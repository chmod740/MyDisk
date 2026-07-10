from django.db import migrations, models


condition = (
    models.Q(file__isnull=False, folder__isnull=True, bucket__isnull=True)
    | models.Q(file__isnull=True, folder__isnull=False, bucket__isnull=True)
    | models.Q(file__isnull=True, folder__isnull=True, bucket__isnull=False)
)
try:
    target_constraint = models.CheckConstraint(
        name='sharelink_exactly_one_target', condition=condition,
    )
except TypeError:
    target_constraint = models.CheckConstraint(
        name='sharelink_exactly_one_target', check=condition,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('sharing', '0001_initial'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='sharelink',
            constraint=target_constraint,
        ),
    ]
