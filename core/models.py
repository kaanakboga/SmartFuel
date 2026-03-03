from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import models


class GeneralSetting(models.Model):
    name = models.CharField(default="", max_length=255, blank=True)
    description = models.CharField(default="", max_length=254, blank=True)
    parameter = models.CharField(default="", max_length=254, blank=True)
    updated_date = models.DateTimeField(auto_now=True, blank=True)
    create_date = models.DateTimeField(auto_now_add=True, blank=True)

    def __str__(self) -> str:
        return self.name


class Ship(models.Model):
    name = models.CharField(max_length=255)
    ship_type = models.CharField(max_length=255)
    gt = models.IntegerField()
    fuel_type = models.CharField(max_length=255)
    emission_level = models.DecimalField(max_digits=10, decimal_places=2)
    compliance_strategy = models.CharField(max_length=255)

    def __str__(self) -> str:
        return f"{self.name} ({self.ship_type})"


class Fuel(models.Model):
    fuel_class = models.CharField(max_length=100, blank=True, default="")
    fuel_type = models.CharField(max_length=255, unique=True)

    # MJ/kg
    lhv_mj_per_kg = models.DecimalField(max_digits=12, decimal_places=6)

    # gCO2e/MJ
    wtw_total_gco2e_per_mj = models.DecimalField(max_digits=12, decimal_places=6)

    # opsiyonel alanlar
    cf_gco2_per_gfuel = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    ttw_co2_gco2_per_mj = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    wtt_plus_nonco2_gco2e_per_mj = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    def __str__(self) -> str:
        return self.fuel_type


class Port(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=2, blank=True, default="")
    is_eu = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class VoyageLeg(models.Model):
    voyage_report_type_name = models.CharField(max_length=120, blank=True, default="")
    distance = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)

    vrn = models.CharField(max_length=20, unique=True, blank=True)

    departure_port = models.ForeignKey(Port, on_delete=models.PROTECT, related_name="departures")
    arrival_port = models.ForeignKey(Port, on_delete=models.PROTECT, related_name="arrivals")

    departure_dt = models.DateTimeField()
    arrival_dt = models.DateTimeField()

    # Shore power (MJ) - intensity paydasına girecek, emisyon 0
    shore_power_energy_mj = models.DecimalField(
        max_digits=18, decimal_places=3, null=True, blank=True, default=0
    )

    created_at = models.DateTimeField(auto_now_add=True)

    fuels = models.ManyToManyField(Fuel, through="VoyageLegFuel", related_name="voyage_legs")

    def save(self, *args, **kwargs):
        if not self.vrn:
            last = VoyageLeg.objects.order_by("-id").first()
            next_no = (last.id + 1) if last else 1
            self.vrn = f"UART-{next_no:06d}"
        super().save(*args, **kwargs)

        if hasattr(self, "_fuel_amount_cache"):
            delattr(self, "_fuel_amount_cache")

    @property
    def route_leg(self) -> str:
        return f"{self.departure_port.code}-{self.arrival_port.code}"

    @property
    def route_leg_type(self) -> str:
        dep_eu = self.departure_port.is_eu
        arr_eu = self.arrival_port.is_eu
        if dep_eu and arr_eu:
            return "EU/EU"
        if dep_eu and not arr_eu:
            return "EU/non EU"
        if (not dep_eu) and arr_eu:
            return "non EU/EU"
        return "non EU/non EU"

    @property
    def scope_factor(self) -> Optional[Decimal]:
        t = self.route_leg_type
        if t == "EU/EU":
            return Decimal("1")
        if t in ("EU/non EU", "non EU/EU"):
            return Decimal("0.5")
        return None

    _FUEL_KEY_MAP = {
        "HFO": ["HFO (Heavy Fuel Oil)", "HFO"],
        "LFO": ["LFO (Light Fuel Oil)", "LFO"],
        "MGO": ["MGO / MDO", "MGO", "MDO"],
        "VLSFO": ["VLSFO (Very Low Sulfur Fuel Oil)", "VLSFO"],

        # LNG varyantlarını da ekle
        "LNG": ["LNG", "LNG (Otto MS)", "LNG (Diesel SS)"],

    }

    def _build_fuel_amount_cache(self) -> dict[str, Decimal]:
        cache = {k: Decimal("0") for k in self._FUEL_KEY_MAP.keys()}
        for item in self.fuel_items.select_related("fuel").all():
            if not item.fuel:
                continue
            amt = item.amount_kg or Decimal("0")
            if amt == 0:
                continue
            ft = (item.fuel.fuel_type or "").strip()
            for k, names in self._FUEL_KEY_MAP.items():
                if ft in names:
                    cache[k] += amt
                    break
        return cache

    def _fuel_amount_kg_by_key(self, key: str) -> Decimal:
        if not hasattr(self, "_fuel_amount_cache"):
            self._fuel_amount_cache = self._build_fuel_amount_cache()
        return self._fuel_amount_cache.get(key, Decimal("0"))

    def _fuel_energy_mj_by_key(self, key: str) -> Optional[Decimal]:
        scope = self.scope_factor
        if scope is None:
            return None

        names = self._FUEL_KEY_MAP.get(key, [])
        if not names:
            return Decimal("0")

        energy = Decimal("0")
        for item in self.fuel_items.select_related("fuel").all():
            if not item.fuel:
                continue
            ft = (item.fuel.fuel_type or "").strip()
            if ft in names:
                amt = item.amount_kg or Decimal("0")
                lhv = item.fuel.lhv_mj_per_kg or Decimal("0")
                energy += (amt * lhv)

        return energy * scope

    @property
    def total_hfo_kg(self) -> Decimal:
        return self._fuel_amount_kg_by_key("HFO")

    @property
    def total_lfo_kg(self) -> Decimal:
        return self._fuel_amount_kg_by_key("LFO")

    @property
    def total_mgo_kg(self) -> Decimal:
        return self._fuel_amount_kg_by_key("MGO")

    @property
    def total_vlsfo_kg(self) -> Decimal:
        return self._fuel_amount_kg_by_key("VLSFO")

    @property
    def total_lng_kg(self):
        return self._fuel_amount_kg_by_key("LNG")

    @property
    def hfo_energy_mj(self) -> Optional[Decimal]:
        return self._fuel_energy_mj_by_key("HFO")

    @property
    def lfo_energy_mj(self) -> Optional[Decimal]:
        return self._fuel_energy_mj_by_key("LFO")

    @property
    def mgo_energy_mj(self) -> Optional[Decimal]:
        return self._fuel_energy_mj_by_key("MGO")

    @property
    def vlsfo_energy_mj(self) -> Optional[Decimal]:
        return self._fuel_energy_mj_by_key("VLSFO")

    @property
    def lng_energy_mj(self):
        return self._fuel_energy_mj_by_key("LNG")

    @property
    def total_ghg_gco2e(self) -> Optional[Decimal]:
        scope = self.scope_factor
        if scope is None:
            return None

        total = Decimal("0")

        for item in self.fuel_items.select_related("fuel").all():
            if not item.fuel:
                continue
            amt = item.amount_kg or Decimal("0")
            if amt == 0:
                continue

            ft_upper = (item.fuel.fuel_type or "").upper()

            # LNG component hesap
            # LNG component hesap
            if "LNG" in ft_upper:
                GWP_CH4 = Decimal("28")
                GWP_N2O = Decimal("265")

                lhv = item.fuel.lhv_mj_per_kg or Decimal("0")
                if lhv == 0:
                    return None

                # Enerji (scope'suz)
                e_mj_raw = amt * lhv

                # A) WTT + upstream non-CO2 (g/MJ) -> DB'den
                wtt_factor = item.fuel.wtt_plus_nonco2_gco2e_per_mj
                if wtt_factor is None:
                    # DB boşsa fallback (senin tablodaki LNG WTT)
                    wtt_factor = Decimal("18.5")
                wtt_g = e_mj_raw * wtt_factor

                # B) TTW CO2 (g/MJ) -> DB'den (varsa)
                ttw_co2_factor = item.fuel.ttw_co2_gco2_per_mj
                if ttw_co2_factor is None:
                    # yoksa cf üzerinden türet
                    cf = item.fuel.cf_gco2_per_gfuel or Decimal("0")  # gCO2/gFuel (kg/kg gibi)
                    # cf burada "kg/kg" mantığında tutuluyorsa (2.75 gibi), g/kg'ye çevir
                    co2_g_per_kg = cf * Decimal("1000")
                    ttw_co2_factor = co2_g_per_kg / lhv
                co2_g = e_mj_raw * ttw_co2_factor

                # C) CH4 slip (%)
                slip_pct = (item.ch4_slip_pct or Decimal("0"))
                ch4_mass_kg = amt * (slip_pct / Decimal("100"))
                ch4_g = ch4_mass_kg * GWP_CH4 * Decimal("1000")

                # D) N2O factor (kg N2O / kg fuel)
                n2o_factor = (item.n2o_factor or Decimal("0"))
                n2o_mass_kg = amt * n2o_factor
                n2o_g = n2o_mass_kg * GWP_N2O * Decimal("1000")

                total += (wtt_g + co2_g + ch4_g + n2o_g) * scope

            else:
                # diğer yakıtlar: g/MJ
                try:
                    e_mj = (amt * item.fuel.lhv_mj_per_kg) * scope
                except (InvalidOperation, ZeroDivisionError):
                    return None
                total += e_mj * item.fuel.wtw_total_gco2e_per_mj

        return total

    @property
    def total_ghg_tco2e(self) -> Optional[Decimal]:
        val = self.total_ghg_gco2e
        if val is None:
            return None
        return val / Decimal("1000000")

    @property
    def total_energy_mj_scoped(self) -> Optional[Decimal]:
        scope = self.scope_factor
        if scope is None:
            return None

        fuel_energy = Decimal("0")
        for item in self.fuel_items.select_related("fuel").all():
            if not item.fuel:
                continue
            amt = item.amount_kg or Decimal("0")
            if amt == 0:
                continue

            lhv = item.fuel.lhv_mj_per_kg or Decimal("0")
            fuel_energy += (amt * lhv) * scope

        shore = (self.shore_power_energy_mj or Decimal("0")) * scope
        return fuel_energy + shore

    @property
    def ghg_intensity_g_per_mj(self) -> Optional[Decimal]:
        e = self.total_energy_mj_scoped
        if e is None or e == 0:
            return None
        g = self.total_ghg_gco2e
        if g is None:
            return None
        return g / e

    def __str__(self) -> str:
        return f"{self.vrn} {self.route_leg}"


class VoyageLegFuel(models.Model):
    voyage_leg = models.ForeignKey(VoyageLeg, on_delete=models.CASCADE, related_name="fuel_items")
    fuel = models.ForeignKey(Fuel, on_delete=models.PROTECT)
    amount_kg = models.DecimalField(max_digits=18, decimal_places=3, default=0)

    LNG_ENGINE_CHOICES = [
        ("OTTO", "Otto"),
        ("DIESEL", "Diesel"),
        ("CERT", "Certified actual"),
    ]

    lng_engine_mode = models.CharField(max_length=10, choices=LNG_ENGINE_CHOICES, null=True, blank=True)

    # % slip
    ch4_slip_pct = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)

    # oran (kg N2O / kg fuel gibi)
    n2o_factor = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)

    class Meta:
        unique_together = ("voyage_leg", "fuel")

    def is_lng(self) -> bool:
        ft = (self.fuel.fuel_type or "").upper()
        return "LNG" in ft

    def clean(self):
        super().clean()

        # LNG değilse bu alanlar boş olmalı
        if not self.is_lng():
            if self.lng_engine_mode:
                raise ValidationError({"lng_engine_mode": "Bu alan sadece LNG için kullanılabilir."})
            if self.ch4_slip_pct is not None:
                raise ValidationError({"ch4_slip_pct": "Bu alan sadece LNG için kullanılabilir."})
            if self.n2o_factor is not None:
                raise ValidationError({"n2o_factor": "Bu alan sadece LNG için kullanılabilir."})
            return

        # LNG ise engine mode fuel_type'tan otomatik belirleniyor.
        ft = ((self.fuel.fuel_type or "") if self.fuel else "").upper()

        auto_mode = None
        if "DIESEL" in ft:
            auto_mode = "DIESEL"
        elif "OTTO" in ft:
            auto_mode = "OTTO"
        elif "CERT" in ft or "CERTIFIED" in ft:
            auto_mode = "CERT"

        # eğer yakaladık ise instance'a yaz
        if auto_mode:
            self.lng_engine_mode = auto_mode

        # Certified actual seçeneği kullanıyorsan, o zaman kullanıcı slip/n2o girmeli
        if self.lng_engine_mode == "CERT":
            if self.ch4_slip_pct is None:
                raise ValidationError({"ch4_slip_pct": "Certified actual için CH4 slip girilmesi zorunlu."})
            if self.n2o_factor is None:
                raise ValidationError({"n2o_factor": "Certified actual için N2O factor girilmesi zorunlu."})

    def save(self, *args, **kwargs):
        # LNG değilse direkt kaydet
        if not self.is_lng():
            return super().save(*args, **kwargs)

        ft_upper = ((self.fuel.fuel_type or "") if self.fuel else "").upper()

        # Fuel'dan engine mode'u otomatik belirle
        if "DIESEL" in ft_upper:
            self.lng_engine_mode = "DIESEL"
        elif "OTTO" in ft_upper:
            self.lng_engine_mode = "OTTO"
        elif "CERT" in ft_upper or "CERTIFIED" in ft_upper:
            self.lng_engine_mode = "CERT"
        else:
            # LNG ama isim yakalanmadıysa - boş bırakma, otto fallback (istersen)
            self.lng_engine_mode = "OTTO"

        # Önceki fuel'u yakala (fuel değişince defaultlar yeniden basılsın)
        prev_fuel_id = None
        if self.pk:
            prev_fuel_id = (
                VoyageLegFuel.objects
                .filter(pk=self.pk)
                .values_list("fuel_id", flat=True)
                .first()
            )
        fuel_changed = (prev_fuel_id is not None and prev_fuel_id != self.fuel_id)

        # CERT: kullanıcı girecekse burada override ETME (istersen)
        # Ama sen "hiç seçim olmasın, otomatik gelsin" diyorsun.
        # CERT seçeneği kullanmayacaksan bu blok seni etkilemez.
        if self.lng_engine_mode == "CERT":
            return super().save(*args, **kwargs)

        # Otto/Diesel defaultlarını bas (yeni kayıt veya fuel değişimi)
        if self._state.adding or fuel_changed:
            if self.lng_engine_mode == "OTTO":
                self.ch4_slip_pct = Decimal("3.1")
                self.n2o_factor = Decimal("0.00011")
            elif self.lng_engine_mode == "DIESEL":
                self.ch4_slip_pct = Decimal("0.2")
                self.n2o_factor = Decimal("0.00011")

        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.voyage_leg.vrn} - {self.fuel.fuel_type} ({self.amount_kg} kg)"