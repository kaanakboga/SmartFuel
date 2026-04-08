from django.contrib import admin
from .models import GeneralSetting, Ship, Port, Fuel, VoyageLeg, VoyageLegFuel
from django.contrib.admin.sites import site
from .models import ComplianceHistory


@admin.register(GeneralSetting)
class GeneralSettingAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description", "parameter", "updated_date", "create_date")
    search_fields = ("name", "description", "parameter")


@admin.register(Ship)
class ShipAdmin(admin.ModelAdmin):
    list_display = ("name", "ship_type", "gt", "emission_level", "compliance_strategy")
    search_fields = ("name", "ship_type")
    list_filter = ("compliance_strategy",)


@admin.register(Port)
class PortAdmin(admin.ModelAdmin):
    search_fields = ("code", "name", "country")
    list_display = ("code", "name", "country", "is_eu")
    list_filter = ("is_eu", "country")


@admin.register(Fuel)
class FuelAdmin(admin.ModelAdmin):
    list_display = (
        "fuel_type",
        "fuel_class",
        "fuel_group",
        "lhv_mj_per_kg",
        "wtt_plus_nonco2_gco2e_per_mj",
        "ttw_co2_gco2_per_mj",
        "cf_gco2_per_gfuel",
        "cf_ch4_ratio",
        "cf_n2o_ratio",
        "wtw_total_gco2e_per_mj",
    )
    search_fields = ("fuel_type", "fuel_class", "fuel_group")
    list_filter = ("fuel_group", "fuel_class")


class VoyageLegFuelInline(admin.StackedInline):
    model = VoyageLegFuel
    extra = 1
    autocomplete_fields = ("fuel",)

    # CH4/N2O formda dursun ki LNG seçince doldurabilelim,
    # ama JS ile LNG değilse gizleyeceğiz.
    fields = ("fuel", "amount_kg", "ch4_slip_pct", "n2o_factor")

    class Media:
        js = ("core/js/voyage_leg_fuel_inline_toggle.js",)


@admin.register(VoyageLeg)
class VoyageLegAdmin(admin.ModelAdmin):
    list_display = (
        "vrn",
        "ship",
        "route_leg",
        "route_leg_type",
        "departure_port",
        "arrival_port",
        "departure_dt",
        "arrival_dt",
        "scope_factor",
        "total_energy_mj_scoped",
        "total_ghg_tco2e",
        "ghg_intensity_g_per_mj",
    )
    search_fields = ("vrn", "departure_port__code", "arrival_port__code", "ship__name")
    list_filter = ("departure_port__is_eu", "arrival_port__is_eu")
    readonly_fields = ("vrn",)
    inlines = [VoyageLegFuelInline]
    # VoyageLegAdmin içinde:
    list_display = ("vrn", "ship", "departure_port", "arrival_port", "departure_dt")

# Global admin JS (inline Media bazen yüklenmiyor, bunu kesin yükler)
class AdminGlobalMedia:
    class Media:
        js = ("core/js/voyage_leg_fuel_inline_toggle.js",)

@admin.register(ComplianceHistory)
class ComplianceHistoryAdmin(admin.ModelAdmin):
    list_display = ("ship", "year", "action_taken", "final_balance_tco2e", "penalty_multiplier_level", "penalty_multiplier", "penalty_eur")
    list_filter = ("action_taken", "year", "ship")
    search_fields = ("ship__name",)

site._global_media = AdminGlobalMedia.Media
# IMPORTANT:
# VoyageLegFuel'u ayrı admin sayfasından kaldırıyoruz.
# Çünkü asıl doğru kullanım inline üzerinden.
# Böylece soldaki menüde "Voyage leg fuels" da kaybolur.
# (Django admin otomatik olarak register edilmez.)