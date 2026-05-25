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

# def calculate_end_date(start_date, days):
#     """Return end date after advancing `days` working days from `start_date`.

#     Accepts `start_date` as a `date`, `datetime`, or ISO/date string.
#     Skips Sundays when counting working days.
#     """
#     from datetime import datetime, date

#     # Normalize start_date to a date object
#     if isinstance(start_date, str):
#         try:
#             current_date = datetime.fromisoformat(start_date).date()
#         except Exception:
#             # fallback to common YYYY-MM-DD format
#             current_date = datetime.strptime(start_date, '%Y-%m-%d').date()
#     elif isinstance(start_date, datetime):
#         current_date = start_date.date()
#     elif isinstance(start_date, date):
#         current_date = start_date
#     else:
#         raise TypeError('start_date must be a date, datetime, or ISO date string')

#     remaining_days = int(days)
#     remaining_days -= 1
#     while remaining_days > 0:
#         current_date = current_date + timedelta(days=1)
#         # skip Sundays (weekday() == 6)
#         if current_date.weekday() != 6:
#             remaining_days -= 1
#     return current_date

# --- Automatic end_date computation and signals ---

def calculate_end_date(start_date, days):

    from datetime import datetime, date, timedelta

    # Normalize start_date to a date object
    if isinstance(start_date, str):
        try:
            current = datetime.fromisoformat(start_date).date()
        except Exception:
            from datetime import datetime as _dt

            current = _dt.strptime(start_date, '%Y-%m-%d').date()
    elif isinstance(start_date, datetime):
        current = start_date.date()
    elif isinstance(start_date, date):
        current = start_date
    else:
        raise TypeError('start_date must be date, datetime, or ISO date string')

    total_days = int(days)

    # 0 or 1 day means same date
    if total_days <= 1:
        return current

    # For >1 day: advance (total_days - 1) working days, skipping Sundays.
    remaining = total_days - 1

    while remaining > 0:
        current = current + timedelta(days=1)
        # Skip Sundays (weekday() == 6)
        if current.weekday() != 6:
            remaining -= 1

    return current


def _compute_order_final_end_date(order):
    """Compute the expected final end_date for an Order.

    Uses the same pipeline rules as the UI: capacity -> days via ceil,
    SLA rules (0 or 1 = same day, >1 = add working days), and skips Sundays.
    Returns a date or None when order has no processes/starts.
    """
    from math import ceil
    from datetime import timedelta

    if not order or not getattr(order, 'start_date', None):
        return None

    # Default pipeline steps (name, sla or capacity)
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

    # Load overrides from DB ProcessStep records
    overrides_qs = ProcessStep.objects.filter(order=order)
    overrides = {p.process_name: p.sla_days for p in overrides_qs}

    current = order.start_date
    final_end = current

    for step in default_steps:
        name = step['name']

        # Determine days for this step
        if name == 'CAD':
            sla_value = 3 if getattr(order, 'style_type', 'New') == 'Repeat' else 7
            sla = overrides.get(name, sla_value)
            days = ceil(sla) if sla and sla > 0 else 0
        elif 'capacity' in step:
            capacity = step.get('capacity')
            if capacity and getattr(order, 'quantity', 0):
                days = ceil(order.quantity / capacity)
                if days <= 0 and order.quantity > 0:
                    days = 1
            else:
                days = 0
            sla_override = overrides.get(name)
            if sla_override is not None:
                days = ceil(sla_override)
        else:
            sla = overrides.get(name, step.get('sla', 0))
            days = ceil(sla) if sla and sla > 0 else 0

        # Calculate end date for this step
        if days > 0:
            end = calculate_end_date(current, days)
        else:
            end = current

        final_end = end

        # Compute next step start: same day if this step is 0-days, else next working day
        if days == 0:
            current = end
        else:
            next_day = end + timedelta(days=1)
            if next_day.weekday() == 6:
                next_day = next_day + timedelta(days=1)
            current = next_day

    return final_end


from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


@receiver(post_save, sender=Order)
def _order_post_save(sender, instance, **kwargs):
    """After an Order is saved, compute and persist its end_date if missing or outdated."""
    final = _compute_order_final_end_date(instance)
    # Only auto-set end_date when it's empty (allow manual admin edits to persist)
    if final and instance.end_date is None:
        # update without triggering another save signal loop
        sender.objects.filter(pk=instance.pk).update(end_date=final)


@receiver(post_save, sender=ProcessStep)
def _processstep_post_save(sender, instance, **kwargs):
    """When a ProcessStep is added/updated, recompute the related Order end_date."""
    order = instance.order
    final = _compute_order_final_end_date(order)
    # Only update Order.end_date if it's not been set manually.
    if final and order.end_date is None:
        Order.objects.filter(pk=order.pk).update(end_date=final)


@receiver(post_delete, sender=ProcessStep)
def _processstep_post_delete(sender, instance, **kwargs):
    """When a ProcessStep is deleted, recompute the related Order end_date."""
    order = instance.order
    final = _compute_order_final_end_date(order)
    if final and order.end_date is None:
        Order.objects.filter(pk=order.pk).update(end_date=final)