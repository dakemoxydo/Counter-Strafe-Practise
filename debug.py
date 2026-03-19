from config import Config
c = Config()
c.set('thresholds', 'min_shot_delay', value=0.0)
c.save()
print("Reset min_shot_delay to 0.0")
