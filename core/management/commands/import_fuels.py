from decimal import Decimal, InvalidOperation
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from core.models import Fuel


def d(val: str | None) -> Decimal | None:
    if val is None:
        return None
    val = str(val).strip()
    if val == "":
        return None
    try:
        return Decimal(val)
    except InvalidOperation:
        return None


class Command(BaseCommand):
    help = "Import fuels from CSV into Fuel table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default="data/liquid_fossil_fuels_wtw_split_v2.csv",
            help="Path to CSV file",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["path"])
        if not csv_path.exists():
            raise CommandError(f"CSV not found: {csv_path}")

        model_fields = {f.name for f in Fuel._meta.fields}

        key_field = "fuel_type" if "fuel_type" in model_fields else "name"
        fuel_class_field = "fuel_class" if "fuel_class" in model_fields else None

        lhv_field = "lhv_mj_per_kg" if "lhv_mj_per_kg" in model_fields else None

        # cf (gCO2/gFuel or t/t - sen ne koyduysan DB'ye aynen yazar)
        cf_field = "cf_gco2_per_gfuel" if "cf_gco2_per_gfuel" in model_fields else None

        # wtw
        if "wtw_total_gco2e_per_mj" in model_fields:
            wtw_field = "wtw_total_gco2e_per_mj"
        elif "wtw_ef_gco2e_per_mj" in model_fields:
            wtw_field = "wtw_ef_gco2e_per_mj"
        else:
            wtw_field = None

        # ttw
        if "ttw_co2_gco2_per_mj" in model_fields:
            ttw_field = "ttw_co2_gco2_per_mj"
        elif "ttw_ef_gco2e_per_mj" in model_fields:
            ttw_field = "ttw_ef_gco2e_per_mj"
        else:
            ttw_field = None

        # wtt
        if "wtt_plus_nonco2_gco2e_per_mj" in model_fields:
            wtt_field = "wtt_plus_nonco2_gco2e_per_mj"
        elif "wtt_ef_gco2e_per_mj" in model_fields:
            wtt_field = "wtt_ef_gco2e_per_mj"
        else:
            wtt_field = None

        created = 0
        updated = 0
        skipped = 0

        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.stdout.write(f"CSV columns: {reader.fieldnames}")

            for row in reader:
                key = (row.get("fuel_type") or "").strip()
                if not key:
                    skipped += 1
                    continue

                defaults = {}

                if fuel_class_field:
                    defaults[fuel_class_field] = (row.get("fuel_class") or "").strip()

                if lhv_field:
                    defaults[lhv_field] = d(row.get("lhv_mj_per_kg"))

                if cf_field:
                    defaults[cf_field] = d(row.get("cf_gco2_per_gfuel"))

                if wtw_field:
                    defaults[wtw_field] = d(row.get("wtw_total_gco2e_per_mj"))

                if ttw_field:
                    defaults[ttw_field] = d(row.get("ttw_co2_gco2_per_mj"))

                if wtt_field:
                    defaults[wtt_field] = d(row.get("wtt_plus_nonco2_gco2e_per_mj"))

                _, was_created = Fuel.objects.update_or_create(
                    **{key_field: key},
                    defaults=defaults
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. created={created}, updated={updated}, skipped={skipped}"
        ))