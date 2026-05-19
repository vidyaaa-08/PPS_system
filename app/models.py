from django.db import models
from datetime import timedelta
# Create your models here.

class Order(models.Model):

    ORDER_TYPES = [
        ('Factory', 'Factory Orders – Stock Replenishment'),
        ('Customer', 'Customer Orders – confirmed customer order'),
        ('PD', 'PD Orders – New Product Development'),
        ('Repair', 'Repair Orders – Repair/Rework items'),
        ('Sample', 'Sample Orders – Stock in alloy with CZ'),
        ('RD', 'R&D Orders – Research & Development'),
        ('ICO', 'ICO Orders – Immediate Customer Orders (urgent execution)'),
    ]

    CATEGORY_TYPES = [
        ('Necklace Set', 'Necklace Set'),
        ('Necklace', 'Necklace (Standalone)'),
        ('Earrings', 'Earrings'),
        ('Pendant Set', 'Pendant Set'),
        ('Pendant', 'Pendant (Standalone)'),
        ('Rings', 'Rings'),
        ('Bracelets', 'Bracelets'),
        ('Bangle', 'Bangle'),
        ('Accessories', 'Accessories'),
    ]

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
    ]

    order_no = models.CharField(max_length=100)

    order_type = models.CharField(
        max_length=50,
        choices=ORDER_TYPES
    )

    category = models.CharField(
        max_length=100,
        choices=CATEGORY_TYPES
    )

    quantity = models.IntegerField()

    start_date = models.DateField()

    end_date = models.DateField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Pending'
    )

    STYLE_TYPE_CHOICES = [
        ('New', 'New Style'),
        ('Repeat', 'Repeat Style'),
    ]

    style_type = models.CharField(max_length=10, choices=STYLE_TYPE_CHOICES, default='New')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.order_no
    
class ProcessStep(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    process_name = models.CharField(max_length=100)
    sla_days = models.FloatField()
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=50, default="Pending")

    def __str__(self):
        return self.process_name

def calculate_end_date(start_date, days):
    from datetime import timedelta

    current_date = start_date
    remaining_days = int(days)

    while remaining_days > 0:
        current_date += timedelta(days=1)

        # Sunday skip
        if current_date.weekday() != 6:
            remaining_days -= 1

    return current_date

def _compute_order_final_end_date(order):
    import math

    default_steps = [
        {'name': 'Order Generation', 'sla': 1},
        {'name': 'PPC Planning', 'sla': 0},
        {'name': 'CAD', 'sla': 7},
        {'name': 'CAM', 'sla': 2},
        {'name': 'Casting / Wax', 'sla': 2},
        {'name': 'Grading / OTECH', 'sla': 1.5},
        {'name': 'Filling', 'capacity': 10},
        {'name': 'Electro Polish', 'capacity': 15},
        {'name': 'Pre-Polish', 'capacity': 15},
        {'name': 'Diamond Bagging', 'sla': 0},
        {'name': 'Setting', 'capacity': 3000},
        {'name': 'Fitting', 'capacity': 10},
        {'name': 'Final Polish', 'capacity': 20},
        {'name': 'Rhodium', 'capacity': 20},
        {'name': 'Ceramic', 'capacity': 30},
        {'name': 'QA', 'capacity': 20},
        {'name': 'Hallmarking', 'sla': 1},
        {'name': 'Certification', 'sla': 0},
        {'name': 'FG (Finished)', 'sla': 0},
    ]

    current = order.start_date
    last_end = None

    for step in default_steps:

        # CAD Logic
        if step['name'] == 'CAD':
            days = 3 if order.style_type == 'Repeat' else 7

        # Capacity Logic
        elif 'capacity' in step:
            days = math.ceil(order.quantity / step['capacity'])

        # Normal SLA
        else:
            days = math.ceil(step['sla'])

        # Calculate end date
        if days > 0:
            end_date = calculate_end_date(current, days)
        else:
            end_date = current

        last_end = end_date

        # IMPORTANT FIX
        current = end_date

    return last_end

def calculate_end_date(start_date, days):
    """Return end date after advancing `days` working days from `start_date`.

    Accepts `start_date` as a `date`, `datetime`, or ISO/date string.
    Skips Sundays when counting working days.
    """
    from datetime import datetime, date

    # Normalize start_date to a date object
    if isinstance(start_date, str):
        try:
            current_date = datetime.fromisoformat(start_date).date()
        except Exception:
            # fallback to common YYYY-MM-DD format
            current_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    elif isinstance(start_date, datetime):
        current_date = start_date.date()
    elif isinstance(start_date, date):
        current_date = start_date
    else:
        raise TypeError('start_date must be a date, datetime, or ISO date string')

    remaining_days = int(days)
    while remaining_days > 0:
        current_date = current_date + timedelta(days=1)
        # skip Sundays 
        if current_date.weekday() != 6:
            remaining_days -= 1
    return current_date


# --- Automatic end_date computation and signals ---
def _compute_order_final_end_date(order):
    """Compute final end date for an Order using 7 core steps and any ProcessStep overrides."""
    if not order.start_date:
        return None

    import math, datetime

    default_steps = [
        {'name': 'Order Generation', 'sla': 1},
        {'name': 'PPC Planning', 'sla': 0},
        {'name': 'CAD', 'sla': 7},
        {'name': 'CAM', 'sla': 2},
        {'name': 'Casting / Wax', 'sla': 2},
        {'name': 'Grading / OTECH', 'sla': 1.5},
        {'name': 'Filling', 'capacity': 10},
        {'name': 'Electro Polish', 'capacity': 15},
        {'name': 'Pre-Polish', 'capacity': 15},
        {'name': 'Diamond Bagging', 'sla': 0},
        {'name': 'Setting', 'capacity': 3000},
        {'name': 'Fitting', 'capacity': 10},
        {'name': 'Final Polish', 'capacity': 20},
        {'name': 'Rhodium', 'capacity': 20},
        {'name': 'Ceramic', 'capacity': 30},
        {'name': 'QA', 'capacity': 20},
        {'name': 'Hallmarking', 'sla': 1},
        {'name': 'Certification', 'sla': 0},
        {'name': 'FG (Finished)', 'sla': 0},
    ]


    steps_qs = ProcessStep.objects.filter(order=order)
    overrides = {p.process_name: p.sla_days for p in steps_qs}

    current = order.start_date
    last_end = None
    for step in default_steps:
        name = step['name']

        # CAD special-case based on order.style_type
        if name == 'CAD':
            sla_value = 3 if getattr(order, 'style_type', 'New') == 'Repeat' else 7
            sla = overrides.get(name, sla_value)
            days = math.ceil(sla) if sla and sla > 0 else 0
        elif 'capacity' in step:
            # capacity-based step: compute days = ceil(quantity / capacity)
            capacity = step.get('capacity')
            if capacity and getattr(order, 'quantity', 0):
                days = math.ceil(order.quantity / capacity)
                # ensure at least 1 day if capacity results in 0 but qty >0
                if days <= 0 and order.quantity > 0:
                    days = 1
            else:
                days = 0
            # override if ProcessStep provides SLA-like override
            sla = overrides.get(name, None)
            if sla is not None:
                days = math.ceil(sla) if sla and sla > 0 else 0
        else:
            sla = overrides.get(name, step.get('sla', 0))
            days = math.ceil(sla) if sla and sla > 0 else 0

        if days > 0:
            end_date = calculate_end_date(current, days)
        else:
            end_date = current

        last_end = end_date

        # advance to next day, skipping Sunday
        next_day = end_date + datetime.timedelta(days=1)
        if next_day.weekday() == 6:
            next_day += datetime.timedelta(days=1)
        current = next_day

    return last_end


from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


@receiver(post_save, sender=Order)
def _order_post_save(sender, instance, **kwargs):
    """After an Order is saved, compute and persist its end_date if missing or outdated."""
    final = _compute_order_final_end_date(instance)
    if final and instance.end_date is None:
        sender.objects.filter(pk=instance.pk).update(end_date=final)


@receiver(post_save, sender=ProcessStep)
def _processstep_post_save(sender, instance, **kwargs):
    """When a ProcessStep is added/updated, recompute the related Order end_date."""
    order = instance.order
    final = _compute_order_final_end_date(order)
    if final and order.end_date is None:
        Order.objects.filter(pk=order.pk).update(end_date=final)


@receiver(post_delete, sender=ProcessStep)
def _processstep_post_delete(sender, instance, **kwargs):
    """When a ProcessStep is deleted, recompute the related Order end_date."""
    order = instance.order
    final = _compute_order_final_end_date(order)
    if final and order.end_date is None:
        Order.objects.filter(pk=order.pk).update(end_date=final)