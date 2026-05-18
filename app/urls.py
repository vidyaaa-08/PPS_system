from django.urls import path
from . import views

urlpatterns = [
    path('index', views.index, name='index'),
    path('signin/', views.sigin, name='signin'),
    path('base/', views.base, name='base'),
    path('register/', views.register, name='register'),
    path('', views.dashboard, name='dashboard'),
    path('create_order/', views.create_order, name='create_order'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot', views.forgot, name='forgot'),
]