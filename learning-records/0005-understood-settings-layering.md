# Understood settings layering

The learner explained that `prod.py` receives shared configuration from `base.py`. The model is
now refined to: Django imports the selected environment module first, and that module imports the
common base settings before overriding environment-specific values.
