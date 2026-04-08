from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone



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
    emission_level = models.DecimalField(max_digits=10, decimal_places=2)
    compliance_strategy = models.CharField(max_length=255)

    def __str__(self) -> str:
        return f"{self.name} ({self.ship_type})"


class Fuel(models.Model):
    """
    Default (reference) fuel factors used by the calculator.
    Non-CO2 factors (CH4/N2O) are stored as ratios (kg gas / kg fuel).
    """
    FUEL_GROUP_CHOICES = [
        ("FOSSIL", "Fossil"),
        ("BIOFUEL", "Biofuel"),
        ("RFNBO", "RFNBO"),
        ("SHORE_POWER", "Shore power"),
    ]

    fuel_class = models.CharField(max_length=100, blank=True, default="")
    fuel_group = models.CharField(max_length=20, choices=FUEL_GROUP_CHOICES, blank=True, default="")

    fuel_type = models.CharField(max_length=255, unique=True)

    # MJ/kg
    lhv_mj_per_kg = models.DecimalField(max_digits=12, decimal_places=6)

    # gCO2e/MJ (legacy/overview value)
    wtw_total_gco2e_per_mj = models.DecimalField(max_digits=12, decimal_places=6)

    # cf (kg CO2 / kg fuel gibi) - CSV ne veriyorsa
    cf_gco2_per_gfuel = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    # gCO2/MJ (CO2 only)
    ttw_co2_gco2_per_mj = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    # gCO2e/MJ (WTT + upstream non-CO2)
    wtt_plus_nonco2_gco2e_per_mj = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    # default non-CO2 factors (kg gas / kg fuel)
    cf_ch4_ratio = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    cf_n2o_ratio = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

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

    # Required intensity snapshot (gCO2e/MJ) -> kayıt anında sabitlenir
    required_intensity_snapshot_g_per_mj = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    fuels = models.ManyToManyField(Fuel, through="VoyageLegFuel", related_name="voyage_legs")

    # --- Required intensity schedule (DNV graph) ---
    @staticmethod
    def required_intensity_by_year(year: int) -> Decimal:
        if 2025 <= year <= 2029:
            return Decimal("89.34")
        if 2030 <= year <= 2034:
            return Decimal("85.69")
        if 2035 <= year <= 2039:
            return Decimal("77.94")
        if 2040 <= year <= 2044:
            return Decimal("62.90")
        if 2045 <= year <= 2049:
            return Decimal("34.64")
        if year >= 2050:
            return Decimal("18.23")
        # 2024 ve öncesi: reference (2020 avg)
        return Decimal("91.16")

    def save(self, *args, **kwargs):
        if not self.vrn:
            last = VoyageLeg.objects.order_by("-id").first()
            next_no = (last.id + 1) if last else 1
            self.vrn = f"UART-{next_no:06d}"

        if self.required_intensity_snapshot_g_per_mj is None:
            year = self.departure_dt.year if self.departure_dt else timezone.localdate().year
            self.required_intensity_snapshot_g_per_mj = self.required_intensity_by_year(year)

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
        """
        Scope burada duruyor ama HAM enerji/GHG'de kullanılmaz.
        Compliance balance hesabında eligible energy için kullanılır.
        """
        t = self.route_leg_type
        if t == "EU/EU":
            return Decimal("1")
        if t in ("EU/non EU", "non EU/EU"):
            return Decimal("0.5")
        return None  # nonEU/nonEU => 0 eligible

    _FUEL_KEY_MAP = {
        "HFO": ["HFO (Heavy Fuel Oil)", "HFO"],
        "LFO": ["LFO (Light Fuel Oil)", "LFO"],
        "MGO": ["MGO / MDO", "MGO", "MDO"],
        "VLSFO": ["VLSFO (Very Low Sulfur Fuel Oil)", "VLSFO"],
        "LNG": ["LNG", "LNG (Otto MS)", "LNG (Diesel SS)", "LNG (Certified actual)"],
        "FAME": ["FAME_Waste_Oil"],
        "HVO": ["HVO_Forest_Residue"],
        "BIO_LNG": ["Bio_LNG"],
        "BIO_METHANOL": ["Bio_Methanol"],
        "NON_CERT_BIO": ["Non_Certified_Bio"],
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
        """
        HAM enerji (MJ). Scope yok.
        """
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

        return energy

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
    def total_fame_kg(self) -> Decimal:
        return self._fuel_amount_kg_by_key("FAME")

    @property
    def total_hvo_kg(self) -> Decimal:
        return self._fuel_amount_kg_by_key("HVO")

    @property
    def total_bio_lng_kg(self) -> Decimal:
        return self._fuel_amount_kg_by_key("BIO_LNG")

    @property
    def total_bio_methanol_kg(self) -> Decimal:
        return self._fuel_amount_kg_by_key("BIO_METHANOL")

    @property
    def total_non_cert_bio_kg(self) -> Decimal:
        return self._fuel_amount_kg_by_key("NON_CERT_BIO")

    @property
    def fame_energy_mj(self) -> Optional[Decimal]:
        return self._fuel_energy_mj_by_key("FAME")

    @property
    def hvo_energy_mj(self) -> Optional[Decimal]:
        return self._fuel_energy_mj_by_key("HVO")

    @property
    def bio_lng_energy_mj(self) -> Optional[Decimal]:
        return self._fuel_energy_mj_by_key("BIO_LNG")

    @property
    def bio_methanol_energy_mj(self) -> Optional[Decimal]:
        return self._fuel_energy_mj_by_key("BIO_METHANOL")

    @property
    def non_cert_bio_energy_mj(self) -> Optional[Decimal]:
        return self._fuel_energy_mj_by_key("NON_CERT_BIO")

    @property
    def total_ghg_gco2e(self) -> Optional[Decimal]:
        """
        HAM Total GHG (gCO2e). Scope yok.
        Scope sadece compliance balance'ta eligible energy için uygulanacak.
        """
        GWP_CH4 = Decimal("28")
        GWP_N2O = Decimal("265")

        total = Decimal("0")

        for item in self.fuel_items.select_related("fuel").all():
            if not item.fuel:
                continue
            amt = item.amount_kg or Decimal("0")
            if amt == 0:
                continue

            ft_upper = (item.fuel.fuel_type or "").upper()

            # LNG component (WTT + TTW CO2 + CH4 + N2O)
            if "LNG" in ft_upper:
                lhv = item.fuel.lhv_mj_per_kg or Decimal("0")
                if lhv == 0:
                    return None

                e_mj_raw = amt * lhv

                wtt_factor = item.fuel.wtt_plus_nonco2_gco2e_per_mj
                if wtt_factor is None:
                    wtt_factor = Decimal("18.5")
                wtt_g = e_mj_raw * wtt_factor

                ttw_co2_factor = item.fuel.ttw_co2_gco2_per_mj
                if ttw_co2_factor is None:
                    cf = item.fuel.cf_gco2_per_gfuel or Decimal("0")
                    co2_g_per_kg = cf * Decimal("1000")
                    ttw_co2_factor = co2_g_per_kg / lhv
                co2_g = e_mj_raw * ttw_co2_factor

                slip_pct = (item.ch4_slip_pct or Decimal("0"))
                ch4_mass_kg = amt * (slip_pct / Decimal("100"))
                ch4_g = ch4_mass_kg * GWP_CH4 * Decimal("1000")

                n2o_factor = (item.n2o_factor or Decimal("0"))
                n2o_mass_kg = amt * n2o_factor
                n2o_g = n2o_mass_kg * GWP_N2O * Decimal("1000")

                total += (wtt_g + co2_g + ch4_g + n2o_g)
                continue

            # OTHER fuels: WTT + CO2 + CH4 + N2O (default)
            try:
                lhv = item.fuel.lhv_mj_per_kg or Decimal("0")
                if lhv == 0:
                    return None

                e_mj_raw = amt * lhv

                wtt_factor = item.fuel.wtt_plus_nonco2_gco2e_per_mj or Decimal("0")
                wtt_g = e_mj_raw * wtt_factor

                ttw_co2_factor = item.fuel.ttw_co2_gco2_per_mj
                if ttw_co2_factor is None:
                    cf = item.fuel.cf_gco2_per_gfuel or Decimal("0")
                    co2_g_per_kg = cf * Decimal("1000")
                    ttw_co2_factor = co2_g_per_kg / lhv
                co2_g = e_mj_raw * ttw_co2_factor

                ch4_ratio = item.fuel.cf_ch4_ratio or Decimal("0")
                n2o_ratio = item.fuel.cf_n2o_ratio or Decimal("0")

                ch4_g = (amt * ch4_ratio) * GWP_CH4 * Decimal("1000")
                n2o_g = (amt * n2o_ratio) * GWP_N2O * Decimal("1000")

                total += (wtt_g + co2_g + ch4_g + n2o_g)

            except (InvalidOperation, ZeroDivisionError):
                return None

        return total

    @property
    def total_ghg_tco2e(self) -> Optional[Decimal]:
        val = self.total_ghg_gco2e
        if val is None:
            return None
        return val / Decimal("1000000")

    @property
    def total_energy_mj_scoped(self) -> Optional[Decimal]:
        """
        HAM toplam enerji (MJ). Scope yok.
        (İsim şimdilik aynı kalsın, template bozulmasın.)
        """
        fuel_energy = Decimal("0")
        for item in self.fuel_items.select_related("fuel").all():
            if not item.fuel:
                continue
            amt = item.amount_kg or Decimal("0")
            if amt == 0:
                continue
            lhv = item.fuel.lhv_mj_per_kg or Decimal("0")
            fuel_energy += (amt * lhv)

        shore = (self.shore_power_energy_mj or Decimal("0"))
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

    # -----------------------------
    # Compliance (scope burada!)
    # -----------------------------
    @property
    def required_ghg_intensity_g_per_mj(self) -> Optional[Decimal]:
        """
        Snapshot üzerinden gider.
        Böylece ileride yıl değişince eski kayıt required intensity'si değişmez.
        """
        return self.required_intensity_snapshot_g_per_mj

    @property
    def eligible_energy_tj(self) -> Optional[Decimal]:
        """
        ΣEnergy[TJ] = (ham energy MJ) * scope / 1e6
        scope: EU/EU=1, EU/nonEU veya nonEU/EU=0.5, nonEU/nonEU=0
        """
        scope = self.scope_factor
        if scope is None:
            return Decimal("0")

        energy_mj = self.total_energy_mj_scoped
        if energy_mj is None:
            return None

        return (energy_mj * scope) / Decimal("1000000")

    @property
    def compliance_balance_tco2e(self) -> Optional[Decimal]:
        """
        Compliance balance [tCO2e] =
          (Required[g/MJ] - Actual[g/MJ]) * ΣEnergy[TJ]
        """
        tj = self.eligible_energy_tj
        if tj is None or tj == 0:
            return Decimal("0")

        actual = self.ghg_intensity_g_per_mj
        if actual is None:
            return None

        required = self.required_ghg_intensity_g_per_mj
        if required is None:
            return None

        return (required - actual) * tj

    def __str__(self) -> str:
        return f"{self.vrn} {self.route_leg}"

    @property
    def penalty_eur(self):
        """
        Penalty (€) – compliance deficit (CB < 0) varsa hesaplanır.

        Formula (görsel):
          Penalty[€] = |CB[tCO2e]| / ActualIntensity[g/MJ] * (2400 €/tVLSFOeq) / (41000 MJ/tVLSFOeq)
                       * (1 + (consecutive_periods - 1)/10)

        2400/41000 €/MJ = 58536.585... €/TJ  -> dokümanda 58,537 €/TJ
        """
        cb = self.compliance_balance_tco2e
        if cb is None:
            return None

        # Borç yoksa ceza yok
        if cb >= 0:
            return Decimal("0")

        actual_intensity = self.ghg_intensity_g_per_mj
        if actual_intensity is None or actual_intensity == 0:
            return None

        PENALTY_EUR_PER_TJ = Decimal("58537")

        # consecutive periods şimdilik 1 (ship-year takibi gelince güncellenecek)
        consecutive_periods = 1
        multiplier = Decimal("1") + (Decimal(consecutive_periods - 1) / Decimal("10"))

        try:
            return (abs(cb) * PENALTY_EUR_PER_TJ / actual_intensity) * multiplier
        except (InvalidOperation, ZeroDivisionError):
            return None

    ship = models.ForeignKey("Ship", on_delete=models.PROTECT, related_name="voyage_legs", null=True, blank=True)


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

    # % slip (ONLY LNG)
    ch4_slip_pct = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)

    # ratio (kg N2O / kg fuel) (ONLY LNG)
    n2o_factor = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)

    class Meta:
        unique_together = ("voyage_leg", "fuel")

    def is_lng(self) -> bool:
        ft = (self.fuel.fuel_type or "").upper()
        return "LNG" in ft

    def clean(self):
        super().clean()

        if not self.is_lng():
            if self.lng_engine_mode:
                raise ValidationError({"lng_engine_mode": "Bu alan sadece LNG için kullanılabilir."})
            if self.ch4_slip_pct is not None:
                raise ValidationError({"ch4_slip_pct": "Bu alan sadece LNG için kullanılabilir."})
            if self.n2o_factor is not None:
                raise ValidationError({"n2o_factor": "Bu alan sadece LNG için kullanılabilir."})
            return

        ft = ((self.fuel.fuel_type or "") if self.fuel else "").upper()

        auto_mode = None
        if "DIESEL" in ft:
            auto_mode = "DIESEL"
        elif "OTTO" in ft:
            auto_mode = "OTTO"
        elif "CERT" in ft or "CERTIFIED" in ft:
            auto_mode = "CERT"

        if auto_mode:
            self.lng_engine_mode = auto_mode

        if self.lng_engine_mode == "CERT":
            if self.ch4_slip_pct is None:
                raise ValidationError({"ch4_slip_pct": "Certified actual için CH4 slip zorunlu."})
            if self.n2o_factor is None:
                raise ValidationError({"n2o_factor": "Certified actual için N2O factor zorunlu."})

    def save(self, *args, **kwargs):
        if not self.is_lng():
            return super().save(*args, **kwargs)

        ft_upper = ((self.fuel.fuel_type or "") if self.fuel else "").upper()

        if "DIESEL" in ft_upper:
            self.lng_engine_mode = "DIESEL"
        elif "OTTO" in ft_upper:
            self.lng_engine_mode = "OTTO"
        elif "CERT" in ft_upper or "CERTIFIED" in ft_upper:
            self.lng_engine_mode = "CERT"
        else:
            self.lng_engine_mode = "OTTO"

        if self.lng_engine_mode == "CERT":
            return super().save(*args, **kwargs)

        prev_fuel_id = None
        if self.pk:
            prev_fuel_id = (
                VoyageLegFuel.objects.filter(pk=self.pk).values_list("fuel_id", flat=True).first()
            )
        fuel_changed = (prev_fuel_id is not None and prev_fuel_id != self.fuel_id)

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

class ComplianceHistory(models.Model):
    ACTION_CHOICES = [
        ("COMPLIANT", "Compliant"),
        ("BANK", "Banking"),
        ("BORROW", "Borrowing"),
        ("POOL", "Pooling"),
        ("PENALTY", "Penalty Paid"),
    ]

    ship = models.ForeignKey(Ship, on_delete=models.CASCADE, related_name="compliance_history")
    year = models.IntegerField()

    # yıl kapanışındaki net bakiye (tCO2e)
    final_balance_tco2e = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal("0"))

    action_taken = models.CharField(max_length=20, choices=ACTION_CHOICES, default="COMPLIANT")

    # ardışık ceza seviyesi (0=ceza yok, 1=ilk ceza yılı, 2=ikinci ardışık, ...)
    penalty_multiplier_level = models.IntegerField(default=0)

    # 1.00, 1.10, 1.20 ...
    penalty_multiplier = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1.00"))

    penalty_eur = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("ship", "year")
        ordering = ["-year", "ship_id"]

    def __str__(self):
        return f"{self.ship.name} - {self.year} - {self.action_taken}"

    @staticmethod
    def compute_multiplier_for_ship_year(ship_id: int, year: int, current_action: str):
        """
        consecutive penalty mantığı:
        - bu yıl PENALTY ise:
            - geçen yıl da PENALTY ise level+1
            - değilse level=1
        - bu yıl PENALTY değilse zincir kırılır: level=0, multiplier=1.00
        """
        if current_action != "PENALTY":
            return 0, Decimal("1.00")

        prev = ComplianceHistory.objects.filter(ship_id=ship_id, year=year - 1).first()
        if prev and prev.action_taken == "PENALTY":
            level = (prev.penalty_multiplier_level or 1) + 1
        else:
            level = 1

        multiplier = Decimal("1.00") + (Decimal(level - 1) * Decimal("0.10"))
        return level, multiplier

