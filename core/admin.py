from django.contrib import admin
from .models import GeneralSetting, Ship, Port, Fuel, VoyageLeg, VoyageLegFuel, ComplianceHistory

@admin.register(GeneralSetting)
class GeneralSettingAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description", "parameter", "updated_date", "create_date")
    search_fields = ("name", "description", "parameter")

@admin.register(Ship)
class ShipAdmin(admin.ModelAdmin):
    # has_wind_propulsion eklendi
    list_display = ("name", "ship_type", "gt", "has_wind_propulsion", "emission_level", "compliance_strategy")
    search_fields = ("name", "ship_type")
    list_filter = ("compliance_strategy", "has_wind_propulsion")

@admin.register(Port)
class PortAdmin(admin.ModelAdmin):
    search_fields = ("code", "name", "country")
    list_display = ("code", "name", "country", "is_eu")
    list_filter = ("is_eu", "country")

@admin.register(Fuel)
class FuelAdmin(admin.ModelAdmin):
    list_display = (
        "fuel_type",
        "fuel_group",
        "lhv_mj_per_kg",
        "wtt_plus_nonco2_gco2e_per_mj",
        "ttw_co2_gco2_per_mj",
        "cf_ch4_ratio",
        "cf_n2o_ratio",
    )
    search_fields = ("fuel_type", "fuel_group")
    list_filter = ("fuel_group",)

class VoyageLegFuelInline(admin.TabularInline): # Daha temiz görünüm için TabularInline
    model = VoyageLegFuel
    extra = 0
    fields = ("fuel", "amount_kg", "lng_engine_mode", "ch4_slip_pct", "n2o_factor")

@admin.register(VoyageLeg)
class VoyageLegAdmin(admin.ModelAdmin):
    list_display = (
        "vrn",
        "ship",
        "departure_port",
        "arrival_port",
        "departure_dt",
        "compliance_balance_tco2e", # Uyumluluk durumunu ana listede görelim
        "penalty_eur"
    )
    search_fields = ("vrn", "ship__name")
    list_filter = ("departure_dt", "ship")
    readonly_fields = ("vrn", "required_intensity_snapshot_g_per_mj")
    inlines = [VoyageLegFuelInline]

@admin.register(ComplianceHistory)
class ComplianceHistoryAdmin(admin.ModelAdmin):
    # Hata veren 'penalty_multiplier' list_display'den kaldırıldı
    list_display = (
        "ship",
        "year",
        "action_taken",
        "final_balance_tco2e",
        "penalty_multiplier_level",
        "penalty_eur"
    )
    list_filter = ("action_taken", "year", "ship")
    search_fields = ("ship__name",)