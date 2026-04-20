from django.shortcuts import render, redirect
from .models import Ship, VoyageLeg, Fuel
from .models import ComplianceHistory


def index(request):
    return render(request, "index.html")


def login(request):
    return render(request, "login.html")


def forgotpassword(request):
    return render(request, "forgot-password.html")


def register(request):
    return render(request, "register.html")


def tables(request):
    ships = Ship.objects.all()
    return render(request, "tables.html", {"ships": ships})


def cards(request):
    return render(request, "cards.html")


def charts(request):
    return render(request, "charts.html")


def buttons(request):
    return render(request, "buttons.html")


def blank(request):
    return render(request, "blank.html")


def error(request):
    return render(request, "404.html")


def utilities_animation(request):
    return render(request, "utilities-animation.html")


def utilities_border(request):
    return render(request, "utilities-border.html")


def utilities_color(request):
    return render(request, "utilities-color.html")


def utilities_other(request):
    return render(request, "utilities-other.html")


def fleet_list(request):
    ships = Ship.objects.all()
    return render(request, "tables.html", {"ships": ships})


def add_ship(request):
    if request.method == "POST":
        Ship.objects.create(
            name=request.POST.get("name"),
            ship_type=request.POST.get("ship_type"),
            gt=request.POST.get("gt"),
            fuel_type=request.POST.get("fuel_type"),
            emission_level=request.POST.get("emission_level"),
            compliance_strategy=request.POST.get("compliance_strategy"),
        )
        return redirect("fleet_list")
    return redirect("fleet_list")


def voyage_legs_table(request):
    legs = VoyageLeg.objects.select_related("departure_port", "arrival_port").order_by("-departure_dt")
    return render(request, "voyage_legs.html", {"legs": legs})


def voyage_legs_report_table(request):
    legs = (
        VoyageLeg.objects.select_related("departure_port", "arrival_port")
        .prefetch_related("fuel_items__fuel")
        .order_by("-departure_dt")
    )
    return render(request, "voyage_legs_report.html", {"legs": legs})


def fuels_reference_table(request):
    fuels = Fuel.objects.all().order_by("fuel_group", "fuel_type")
    return render(request, "fuels_reference.html", {"fuels": fuels})


# -----------------------------
# FLEXIBILITY (NEW PAGES)
# -----------------------------
def _flex_base_queryset():
    return (
        VoyageLeg.objects.select_related("departure_port", "arrival_port")
        .prefetch_related("fuel_items__fuel")
        .order_by("-departure_dt")
    )


def flex_banking_table(request):
    legs = [v for v in _flex_base_queryset() if (v.compliance_balance_tco2e is not None and v.compliance_balance_tco2e > 0)]
    return render(request, "flex_banking.html", {"legs": legs})


def flex_borrowing_table(request):
    legs = [v for v in _flex_base_queryset() if (v.compliance_balance_tco2e is not None and v.compliance_balance_tco2e < 0)]
    return render(request, "flex_borrowing.html", {"legs": legs})


def flex_pooling_table(request):
    selected_ids = request.POST.getlist('selected_leg_id')
    legs = VoyageLeg.objects.filter(id__in=selected_ids)

    total_balance = sum(l.compliance_balance_tco2e for l in legs)
    total_energy = sum(l.eligible_energy_tj for l in legs)

    # Pool sonrası yeni emisyon yoğunluğu
    # Intensity = (Standard_Intensity * Total_Energy - Total_Balance) / Total_Energy
    # Eğer balance pozitifse intensity düşer, negatifse artar.

    return render(request, "flex_pooling.html", {
        "legs": legs,
        "pool_balance": total_balance,
        "is_compliant": total_balance >= 0
    })
def flex_history_table(request):
    from decimal import Decimal

    legs = (
        VoyageLeg.objects.select_related("ship", "departure_port", "arrival_port")
        .prefetch_related("fuel_items__fuel")
        .exclude(ship__isnull=True)  # ship seçilmemiş seferler history'e girmez
        .order_by("departure_dt")
    )

    # group by (ship_id, year)
    groups = {}
    for leg in legs:
        year = leg.departure_dt.year
        key = (leg.ship_id, year)

        g = groups.get(key)
        if not g:
            g = {
                "ship_id": leg.ship_id,
                "ship_name": leg.ship.name if leg.ship else "-",
                "year": year,
                "cb_sum": Decimal("0"),
                "eligible_tj_sum": Decimal("0"),
                "energy_mj_sum": Decimal("0"),
                "ghg_g_sum": Decimal("0"),
                "has_cb": False,
            }
            groups[key] = g

        cb = leg.compliance_balance_tco2e
        tj = leg.eligible_energy_tj
        e = leg.total_energy_mj_scoped
        ghg = leg.total_ghg_gco2e

        if cb is not None:
            g["cb_sum"] += cb
            g["has_cb"] = True
        if tj is not None:
            g["eligible_tj_sum"] += tj
        if e is not None:
            g["energy_mj_sum"] += e
        if ghg is not None:
            g["ghg_g_sum"] += ghg

    # one row per ship-year
    rows = []
    for (_, _), g in groups.items():
        if not g["has_cb"]:
            continue

        cb_sum = g["cb_sum"]

        # action (MVP)
        if cb_sum > 0:
            action = "BANK"
        elif cb_sum < 0:
            action = "PENALTY"
        else:
            action = "COMPLIANT"

        actual_int = None
        if g["energy_mj_sum"] and g["energy_mj_sum"] != 0:
            actual_int = g["ghg_g_sum"] / g["energy_mj_sum"]  # g/MJ

        rows.append(
            {
                "ship_id": g["ship_id"],
                "ship_name": g["ship_name"],
                "year": g["year"],
                "action": action,
                "final_balance_tco2e": cb_sum,
                "eligible_energy_tj": g["eligible_tj_sum"],
                "actual_intensity_g_per_mj": actual_int,
                "penalty_level": 0,
                "penalty_multiplier": Decimal("1.00"),
                "penalty_eur": None,
            }
        )

    # consecutive penalty chain per ship
    rows_by_ship = {}
    for r in rows:
        rows_by_ship.setdefault(r["ship_id"], []).append(r)

    for ship_id, lst in rows_by_ship.items():
        lst.sort(key=lambda x: x["year"])  # ascending year
        level = 0
        for r in lst:
            if r["action"] == "PENALTY":
                level += 1
                r["penalty_level"] = level
                r["penalty_multiplier"] = Decimal("1.00") + (Decimal(level - 1) * Decimal("0.10"))
            else:
                level = 0
                r["penalty_level"] = 0
                r["penalty_multiplier"] = Decimal("1.00")

            # penalty € (only penalty years)
            if r["action"] == "PENALTY":
                cb = r["final_balance_tco2e"]
                actual_int = r["actual_intensity_g_per_mj"]
                if actual_int is not None and actual_int != 0:
                    PENALTY_EUR_PER_TJ = Decimal("58537")
                    r["penalty_eur"] = (abs(cb) * PENALTY_EUR_PER_TJ / actual_int) * r["penalty_multiplier"]

    # newest first
    rows.sort(key=lambda x: (x["year"], x["ship_name"]), reverse=True)

    return render(request, "flex_history.html", {"rows": rows})