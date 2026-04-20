from __future__ import annotations
from decimal import Decimal, InvalidOperation
from typing import Optional
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# --- GLOBAL YARDIMCI FONKSİYONLAR ---

def get_fueleu_required_intensity(year: int) -> Decimal:
    """DNV White Paper Sayfa 10 - Tablo 1 resmi azaltım oranları."""
    REFERENCE_VALUE = Decimal("91.16")
    if year < 2025:
        reduction_pct = Decimal("0.00")
    elif year < 2030:
        reduction_pct = Decimal("2.00")
    elif year < 2035:
        reduction_pct = Decimal("6.00")
    elif year < 2040:
        reduction_pct = Decimal("14.50")
    elif year < 2045:
        reduction_pct = Decimal("31.00")
    elif year < 2050:
        reduction_pct = Decimal("62.00")
    else:
        reduction_pct = Decimal("80.00")
    return (REFERENCE_VALUE * (1 - (reduction_pct / 100))).quantize(Decimal("0.01"))


# --- MODELLER ---

class GeneralSetting(models.Model):
    name = models.CharField(default="", max_length=255, blank=True)
    description = models.CharField(default="", max_length=254, blank=True)
    parameter = models.CharField(default="", max_length=254, blank=True)
    updated_date = models.DateTimeField(auto_now=True, blank=True)
    create_date = models.DateTimeField(auto_now_add=True, blank=True)

    def __str__(self) -> str: return self.name


class Ship(models.Model):
    name = models.CharField(max_length=255)
    ship_type = models.CharField(max_length=255)
    gt = models.IntegerField()
    emission_level = models.DecimalField(max_digits=10, decimal_places=2)
    compliance_strategy = models.CharField(max_length=255)
    has_wind_propulsion = models.BooleanField(default=False, verbose_name="Rüzgar Destekli Sevk Sistemi")

    def __str__(self) -> str: return f"{self.name} ({self.ship_type})"


class Fuel(models.Model):
    FUEL_GROUP_CHOICES = [("FOSSIL", "Fossil"), ("BIOFUEL", "Biofuel"), ("RFNBO", "RFNBO"),
                          ("SHORE_POWER", "Shore power")]
    fuel_class = models.CharField(max_length=100, blank=True, default="")
    fuel_group = models.CharField(max_length=20, choices=FUEL_GROUP_CHOICES, blank=True, default="")
    fuel_type = models.CharField(max_length=255, unique=True)
    lhv_mj_per_kg = models.DecimalField(max_digits=12, decimal_places=6)
    wtw_total_gco2e_per_mj = models.DecimalField(max_digits=12, decimal_places=6)
    cf_gco2_per_gfuel = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    ttw_co2_gco2_per_mj = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    wtt_plus_nonco2_gco2e_per_mj = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    cf_ch4_ratio = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    cf_n2o_ratio = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    def __str__(self) -> str: return self.fuel_type


class Port(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=2, blank=True, default="")
    is_eu = models.BooleanField(default=False)

    def __str__(self) -> str: return f"{self.code} - {self.name}"


class VoyageLeg(models.Model):
    ship = models.ForeignKey(Ship, on_delete=models.PROTECT, related_name="voyage_legs", null=True, blank=True)
    voyage_report_type_name = models.CharField(max_length=120, blank=True, default="")
    distance = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    vrn = models.CharField(max_length=20, unique=True, blank=True)
    departure_port = models.ForeignKey(Port, on_delete=models.PROTECT, related_name="departures")
    arrival_port = models.ForeignKey(Port, on_delete=models.PROTECT, related_name="arrivals")
    departure_dt = models.DateTimeField()
    arrival_dt = models.DateTimeField()
    shore_power_energy_mj = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True, default=0)
    required_intensity_snapshot_g_per_mj = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    fuels = models.ManyToManyField(Fuel, through="VoyageLegFuel", related_name="voyage_legs")

    def save(self, *args, **kwargs):
        if not self.vrn:
            last = VoyageLeg.objects.order_by("-id").first()
            self.vrn = f"UART-{(last.id + 1 if last else 1):06d}"
        if self.required_intensity_snapshot_g_per_mj is None:
            year = self.departure_dt.year if self.departure_dt else timezone.localdate().year
            self.required_intensity_snapshot_g_per_mj = get_fueleu_required_intensity(year)
        super().save(*args, **kwargs)

    # --- DINAMIK TABLO PROPERTYLERI (Senin HTML için) ---
    def _get_fuel_summary(self, fuel_keyword: str, attr: str):
        items = [i for i in self.fuel_items.all() if fuel_keyword.upper() in i.fuel.fuel_type.upper()]
        if attr == "kg": return sum(i.amount_kg for i in items)
        if attr == "mj": return sum(i.energy_mj for i in items)
        return Decimal("0")

    @property
    def total_hfo_kg(self):
        return self._get_fuel_summary("HFO", "kg")

    @property
    def hfo_energy_mj(self):
        return self._get_fuel_summary("HFO", "mj")

    @property
    def total_lfo_kg(self):
        return self._get_fuel_summary("LFO", "kg")

    @property
    def lfo_energy_mj(self):
        return self._get_fuel_summary("LFO", "mj")

    @property
    def total_mgo_kg(self):
        return self._get_fuel_summary("MGO", "kg")

    @property
    def mgo_energy_mj(self):
        return self._get_fuel_summary("MGO", "mj")

    @property
    def total_vlsfo_kg(self):
        return self._get_fuel_summary("VLSFO", "kg")

    @property
    def vlsfo_energy_mj(self):
        return self._get_fuel_summary("VLSFO", "mj")

    @property
    def total_lng_kg(self):
        return self._get_fuel_summary("LNG", "kg")

    @property
    def lng_energy_mj(self):
        return self._get_fuel_summary("LNG", "mj")

    @property
    def total_fame_kg(self):
        return self._get_fuel_summary("FAME", "kg")

    @property
    def fame_energy_mj(self):
        return self._get_fuel_summary("FAME", "mj")

    @property
    def total_hvo_kg(self):
        return self._get_fuel_summary("HVO", "kg")

    @property
    def hvo_energy_mj(self):
        return self._get_fuel_summary("HVO", "mj")

    @property
    def total_bio_lng_kg(self):
        return self._get_fuel_summary("BIO_LNG", "kg")

    @property
    def bio_lng_energy_mj(self):
        return self._get_fuel_summary("BIO_LNG", "mj")

    @property
    def total_bio_methanol_kg(self):
        return self._get_fuel_summary("BIO_METHANOL", "kg")

    @property
    def bio_methanol_energy_mj(self):
        return self._get_fuel_summary("BIO_METHANOL", "mj")

    @property
    def total_non_cert_bio_kg(self):
        return self._get_fuel_summary("NON_CERT", "kg")

    @property
    def non_cert_bio_energy_mj(self):
        return self._get_fuel_summary("NON_CERT", "mj")

    @property
    def route_leg(self) -> str:
        return f"{self.departure_port.code}-{self.arrival_port.code}"

    @property
    def route_leg_type(self) -> str:
        dep, arr = self.departure_port.is_eu, self.arrival_port.is_eu
        if dep and arr: return "EU/EU"
        if dep or arr: return "EU/non EU" if dep else "non EU/EU"
        return "non EU/non EU"

    @property
    def scope_factor(self) -> Decimal:
        t = self.route_leg_type
        return Decimal("1.0") if t == "EU/EU" else (Decimal("0.5") if "non EU" in t else Decimal("0.0"))

    @property
    def f_wind_reward(self) -> Decimal:
        return Decimal("0.95") if self.ship and self.ship.has_wind_propulsion else Decimal("1.00")

    @property
    def total_energy_mj_scoped(self) -> Decimal:
        fuel_e = sum(item.energy_mj for item in self.fuel_items.all())
        return fuel_e + (self.shore_power_energy_mj or Decimal("0"))

    @property
    def total_ghg_gco2e(self) -> Decimal:
        return sum(item.ghg_gco2e for item in self.fuel_items.all())

    @property
    def total_ghg_tco2e(self) -> Decimal:
        return (self.total_ghg_gco2e / Decimal("1000000")).quantize(Decimal("0.000001"))

    @property
    def ghg_intensity_g_per_mj(self) -> Decimal:
        e = self.total_energy_mj_scoped
        if not e: return Decimal("0")
        raw = self.total_ghg_gco2e / e
        return (raw * self.f_wind_reward).quantize(Decimal("0.01"))

    @property
    def required_ghg_intensity_g_per_mj(self):
        return self.required_intensity_snapshot_g_per_mj

    @property
    def eligible_energy_tj(self) -> Decimal:
        return (self.total_energy_mj_scoped * self.scope_factor) / Decimal("1000000")

    @property
    def compliance_balance_tco2e(self) -> Decimal:
        tj = self.eligible_energy_tj
        if not tj: return Decimal("0")
        return (self.required_ghg_intensity_g_per_mj - self.ghg_intensity_g_per_mj) * tj

    @property
    def max_borrowing_limit(self) -> Decimal:
        return Decimal("0.02") * self.required_ghg_intensity_g_per_mj * self.eligible_energy_tj

    @property
    def penalty_eur(self) -> Decimal:
        cb = self.compliance_balance_tco2e
        if cb >= 0: return Decimal("0")
        actual = self.ghg_intensity_g_per_mj
        if not actual: return Decimal("0")

        n = 1
        prev = ComplianceHistory.objects.filter(ship=self.ship, year=self.departure_dt.year - 1,
                                                action_taken="PENALTY").first()
        if prev: n = prev.penalty_multiplier_level + 1
        multiplier = Decimal("1") + (Decimal(n - 1) / Decimal("10"))

        return (abs(cb) * Decimal("58537") / actual) * multiplier

    def __str__(self) -> str:
        return f"{self.vrn} {self.route_leg}"


class VoyageLegFuel(models.Model):
    voyage_leg = models.ForeignKey(VoyageLeg, on_delete=models.CASCADE, related_name="fuel_items")
    fuel = models.ForeignKey(Fuel, on_delete=models.PROTECT)
    amount_kg = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    lng_engine_mode = models.CharField(max_length=10, null=True, blank=True)
    ch4_slip_pct = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    n2o_factor = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)

    @property
    def energy_mj(self) -> Decimal:
        return (self.amount_kg * self.fuel.lhv_mj_per_kg) if self.fuel else Decimal("0")

    @property
    def ghg_gco2e(self) -> Decimal:
        if not self.fuel or not self.amount_kg: return Decimal("0")
        GWP_CH4, GWP_N2O = Decimal("28"), Decimal("265")
        e_mj = self.energy_mj

        wtt = e_mj * (self.fuel.wtt_plus_nonco2_gco2e_per_mj or Decimal("0"))
        ttw_co2 = e_mj * (self.fuel.ttw_co2_gco2_per_mj or (
            self.fuel.cf_gco2_per_gfuel * 1000 / self.fuel.lhv_mj_per_kg if self.fuel.cf_gco2_per_gfuel else Decimal(
                "0")))

        ch4_g = (self.amount_kg * (
            self.ch4_slip_pct / 100 if self.ch4_slip_pct else self.fuel.cf_ch4_ratio or 0)) * GWP_CH4 * 1000
        n2o_g = (self.amount_kg * (
            self.n2o_factor if self.n2o_factor else self.fuel.cf_n2o_ratio or 0)) * GWP_N2O * 1000
        return wtt + ttw_co2 + ch4_g + n2o_g

    def save(self, *args, **kwargs):
        if "LNG" in self.fuel.fuel_type.upper() and not self.ch4_slip_pct:
            if "OTTO" in self.fuel.fuel_type.upper():
                self.ch4_slip_pct, self.n2o_factor = Decimal("3.1"), Decimal("0.00011")
            else:
                self.ch4_slip_pct, self.n2o_factor = Decimal("0.2"), Decimal("0.00011")
        super().save(*args, **kwargs)


class ComplianceHistory(models.Model):
    ship = models.ForeignKey(Ship, on_delete=models.CASCADE, related_name="compliance_history")
    year = models.IntegerField()
    final_balance_tco2e = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    action_taken = models.CharField(max_length=20, default="COMPLIANT")
    penalty_multiplier_level = models.IntegerField(default=0)
    penalty_multiplier = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1.00"))
    penalty_eur = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta: unique_together = ("ship", "year")