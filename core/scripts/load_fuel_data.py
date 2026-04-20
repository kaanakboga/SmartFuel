# load_fuel_data.py (Özetlenmiş Versiyon)
from decimal import Decimal
from core.models import Fuel

def run():
    fuels = [
        {
            "fuel_type": "HFO",
            "fuel_group": "FOSSIL",
            "lhv_mj_per_kg": Decimal("40.5"),
            "wtw_total_gco2e_per_mj": Decimal("91.6"),
            "cf_gco2_per_gfuel": Decimal("3.114"),
            "ttw_co2_gco2_per_mj": Decimal("76.88"),
            "wtt_plus_nonco2_gco2e_per_mj": Decimal("14.72"),
            "cf_ch4_ratio": Decimal("0.00005"), # DNV Tablo 4
            "cf_n2o_ratio": Decimal("0.00018"),
        },
        {
            "fuel_type": "LNG (Otto MS)",
            "fuel_group": "FOSSIL",
            "lhv_mj_per_kg": Decimal("49.1"),
            "wtw_total_gco2e_per_mj": Decimal("76.4"),
            "cf_gco2_per_gfuel": Decimal("2.75"),
            "ttw_co2_gco2_per_mj": Decimal("56.0"),
            "wtt_plus_nonco2_gco2e_per_mj": Decimal("18.5"),
            # LNG için Slip (metan kaybı) VoyageLegFuel içinde hesaplanıyor
        },
        # Buraya dökümandaki diğer yakıtlar (MGO, LFO, Bio-fuels) eklenecek...
    ]

    for fuel_data in fuels:
        obj, created = Fuel.objects.update_or_create(
            fuel_type=fuel_data['fuel_type'],
            defaults=fuel_data
        )
        print(f"{obj.fuel_type} yüklendi/güncellendi.")