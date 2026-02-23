from django.contrib import admin
from django.urls import path
from core.views import (
    index, login, error, blank, buttons, cards, charts,
    register, tables, utilities_color, utilities_other,
    utilities_border, utilities_animation, forgotpassword,
    fleet_list, add_ship
)
from core.views import voyage_legs_table
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index, name='index'),

    path('login/', login, name='login'),
    path('register/', register, name='register'),
    path('forgotpassword/', forgotpassword, name='forgot_password'),

    path('cards/', cards, name='cards'),
    path('charts/', charts, name='charts'),
    path('tables/', tables, name='tables'),
    path('error/', error, name='error'),
    path('blank/', blank, name='blank'),
    path('buttons/', buttons, name='buttons'),

    path('utilities-color/', utilities_color, name='utilities-color'),
    path('utilities-other/', utilities_other, name='utilities-other'),
    path('utilities-border/', utilities_border, name='utilities-border'),
    path('utilities-animation/', utilities_animation, name='utilities-animation'),

    path('fleet/', fleet_list, name='fleet_list'),
    path('add-ship/', add_ship, name='add_ship'),

    path("voyage-legs/", voyage_legs_table, name="voyage_legs"),

path("voyage-legs-report/", views.voyage_legs_report_table, name="voyage_legs_report"),


]
