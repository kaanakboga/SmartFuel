from django.contrib import admin
from .models import GeneralSetting, Ship, Port, Fuel, VoyageLeg, VoyageLegFuel


@admin.register(GeneralSetting)
class GeneralSettingAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description", "parameter", "updated_date", "create_date")
    search_fields = ("name", "description", "parameter")


@admin.register(Ship)
class ShipAdmin(admin.ModelAdmin):
    list_display = ("name", "ship_type", "gt", "fuel_type", "emission_level", "compliance_strategy")
    search_fields = ("name", "ship_type", "fuel_type")
    list_filter = ("fuel_type", "compliance_strategy")


@admin.register(Port)
class PortAdmin(admin.ModelAdmin):
    search_fields = ("code", "name", "country")
    list_display = ("code", "name", "country", "is_eu")
    list_filter = ("is_eu", "country")


@admin.register(Fuel)
class FuelAdmin(admin.ModelAdmin):
    list_display = ("fuel_type", "fuel_class", "lhv_mj_per_kg", "wtw_total_gco2e_per_mj")
    search_fields = ("fuel_type", "fuel_class")


class VoyageLegFuelInline(admin.TabularInline):
    model = VoyageLegFuel
    extra = 1
    autocomplete_fields = ("fuel",)
    fields = ("fuel", "amount_kg", "ch4_slip_pct", "n2o_factor")  # lng_engine_mode YOK


@admin.register(VoyageLeg)
class VoyageLegAdmin(admin.ModelAdmin):
    list_display = (
        "vrn",
        "route_leg",
        "route_leg_type",
        "departure_dt",
        "arrival_dt",
        "total_ghg_tco2e_display",
    )
    search_fields = ("vrn", "departure_port__code", "arrival_port__code")
    list_filter = ("departure_port__is_eu", "arrival_port__is_eu")
    autocomplete_fields = ("departure_port", "arrival_port")
    inlines = (VoyageLegFuelInline,)

    fields = (
        "voyage_report_type_name",
        "distance",
        "departure_port",
        "arrival_port",
        "departure_dt",
        "arrival_dt",
        "shore_power_energy_mj",
    )

    readonly_fields = ("vrn",)

    @admin.display(description="Total GHG (tCO2e)")
    def total_ghg_tco2e_display(self, obj):
        v = obj.total_ghg_tco2e
        return "-" if v is None else f"{v:.6f}"


@admin.register(VoyageLegFuel)
class VoyageLegFuelAdmin(admin.ModelAdmin):
    list_display = ("voyage_leg", "fuel", "amount_kg", "lng_engine_mode", "ch4_slip_pct", "n2o_factor")
    search_fields = ("voyage_leg__vrn", "fuel__fuel_type")
    list_filter = ("fuel__fuel_type", "lng_engine_mode")
    autocomplete_fields = ("voyage_leg", "fuel")
    fields = ("voyage_leg", "fuel", "amount_kg", "lng_engine_mode", "ch4_slip_pct", "n2o_factor")