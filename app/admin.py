from django.contrib import admin
from .models import Order, ProcessStep


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'order_no',
        'order_type',
        'category',
        'quantity',
        'start_date',
        'created_at',
    )

    list_filter = (
        'order_type',
        'category',
        'start_date',
        'created_at',
    )

    search_fields = (
        'order_no',
        'category',
    )

    ordering = ('-created_at',)


@admin.register(ProcessStep)
class ProcessStepAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'order',
        'process_name',
        'sla_days',
        'start_date',
        'end_date',
        'status',
    )

    list_filter = (
        'status',
        'process_name',
        'start_date',
        'end_date',
    )

    search_fields = (
        'process_name',
        'order__order_no',
    )

    ordering = ('-id',)