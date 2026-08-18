from django.db import models


class Zone(models.Model):
    """Agro-ecological zones za Tanzania"""
    RAIN_PATTERNS = [
        ('chache', 'Mvua Chache'),
        ('wastani', 'Mvua za Wastani'),
        ('nyingi', 'Mvua Nyingi'),
        ('bimodal', 'Mvua Mbili kwa Mwaka'),
    ]

    zone_name = models.CharField(max_length=100, unique=True)
    rain_pattern_simple = models.CharField(max_length=50, choices=RAIN_PATTERNS)
    rainfall_band_mm = models.CharField(max_length=50, blank=True, help_text="e.g. 400-700mm")
    altitude_band_m = models.CharField(max_length=50, blank=True, help_text="e.g. 0-1000m")
    risk_factors = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['zone_name']
        verbose_name = 'Zone'
        verbose_name_plural = 'Zones'

    def __str__(self):
        return self.zone_name


class LocationMapping(models.Model):
    """Unganisha mikoa/wilaya na agro-ecological zones"""
    region_name = models.CharField(max_length=100)
    district_name = models.CharField(max_length=100, blank=True)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='locations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['region_name', 'district_name']
        verbose_name = 'Location Mapping'
        verbose_name_plural = 'Location Mappings'
        unique_together = ['region_name', 'district_name']

    def __str__(self):
        if self.district_name:
            return f"{self.district_name}, {self.region_name} → {self.zone.zone_name}"
        return f"{self.region_name} → {self.zone.zone_name}"


class Crop(models.Model):
    """Mazao yote yanayotumika kwenye mfumo"""
    CROP_GROUPS = [
        ('cereals', 'Nafaka / Cereals'),
        ('legumes', 'Mikunde / Legumes'),
        ('roots', 'Mizizi / Root Crops'),
        ('vegetables', 'Mboga / Vegetables'),
        ('fruits', 'Matunda / Fruits'),
        ('cash_crops', 'Mazao ya Biashara / Cash Crops'),
    ]
    PRIORITY_LEVELS = [(i, str(i)) for i in range(1, 6)]
    STATUS = [('active', 'Active'), ('inactive', 'Inactive')]

    crop_name_sw = models.CharField(max_length=100, verbose_name="Jina la Zao (Kiswahili)")
    crop_name_en = models.CharField(max_length=100, verbose_name="Jina la Zao (English)")
    crop_group = models.CharField(max_length=50, choices=CROP_GROUPS)
    priority_level = models.IntegerField(choices=PRIORITY_LEVELS, default=1)
    active_status = models.CharField(max_length=20, choices=STATUS, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['priority_level', 'crop_name_sw']
        verbose_name = 'Zao'
        verbose_name_plural = 'Mazao'

    def __str__(self):
        return f"{self.crop_name_sw} ({self.crop_name_en})"


class CropProfile(models.Model):
    """Knowledge base ya kila zao kwa kila zone"""
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='profiles')
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='crop_profiles')
    recommended_varieties = models.TextField(blank=True, help_text="Orodha ya mbegu zinazopendekezwa")
    maturity_days_min = models.PositiveIntegerField(null=True, blank=True)
    maturity_days_max = models.PositiveIntegerField(null=True, blank=True)
    planting_window_simple = models.CharField(max_length=200, blank=True, help_text="e.g. Oktoba - Novemba")
    spacing = models.CharField(max_length=100, blank=True, help_text="e.g. 75cm x 25cm")
    planting_method = models.TextField(blank=True)
    fertilizer_planting = models.TextField(blank=True, help_text="Mbolea ya kupandia")
    fertilizer_top_dressing = models.TextField(blank=True, help_text="Mbolea ya juu")
    common_pests = models.TextField(blank=True)
    common_diseases = models.TextField(blank=True)
    common_symptoms = models.TextField(blank=True)
    harvest_window = models.CharField(max_length=200, blank=True)
    storage_notes = models.TextField(blank=True)
    market_notes = models.TextField(blank=True)
    caution_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Crop Profile'
        verbose_name_plural = 'Crop Profiles'
        unique_together = ['crop', 'zone']

    def __str__(self):
        zone_name = self.zone.zone_name if self.zone else "General"
        return f"{self.crop.crop_name_sw} – {zone_name}"


class SeedVariety(models.Model):
    """Aina za mbegu kwa kila zao"""
    MATURITY_CLASSES = [
        ('early', 'Early (chini ya siku 90)'),
        ('medium', 'Medium (siku 90-120)'),
        ('late', 'Late (zaidi ya siku 120)'),
    ]
    VERIFICATION_STATUS = [
        ('verified', 'Verified'),
        ('unverified', 'Unverified'),
        ('pending', 'Pending Review'),
    ]

    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='varieties')
    recommended_zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='seed_varieties')
    variety_name = models.CharField(max_length=100)
    maturity_class = models.CharField(max_length=20, choices=MATURITY_CLASSES, blank=True)
    maturity_days_min = models.PositiveIntegerField(null=True, blank=True)
    maturity_days_max = models.PositiveIntegerField(null=True, blank=True)
    drought_tolerance = models.CharField(max_length=50, blank=True, help_text="High / Medium / Low")
    disease_tolerance = models.CharField(max_length=200, blank=True)
    rainfall_requirement_mm = models.CharField(max_length=50, blank=True)
    altitude_requirement_m = models.CharField(max_length=50, blank=True)
    seed_source = models.CharField(max_length=200, blank=True, help_text="e.g. SEEDCO, Pannar")
    notes = models.TextField(blank=True)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['crop', 'variety_name']
        verbose_name = 'Aina ya Mbegu'
        verbose_name_plural = 'Aina za Mbegu'

    def __str__(self):
        return f"{self.variety_name} ({self.crop.crop_name_sw})"


class Intent(models.Model):
    """Aina za maswali ambayo mfumo unajua"""
    intent_name = models.CharField(max_length=100, unique=True)
    description_sw = models.TextField(help_text="Maelezo ya intent kwa Kiswahili")
    required_entities = models.CharField(max_length=200, blank=True, help_text="e.g. crop, location")
    follow_up_prompt = models.TextField(blank=True, help_text="Swali la kufuatia")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['intent_name']
        verbose_name = 'Intent'
        verbose_name_plural = 'Intents'

    def __str__(self):
        return self.intent_name


class FarmerQuestion(models.Model):
    """Mifano ya maswali ya wakulima na intent zake"""
    crop = models.ForeignKey(Crop, on_delete=models.SET_NULL, null=True, blank=True, related_name='sample_questions')
    intent = models.ForeignKey(Intent, on_delete=models.CASCADE, related_name='sample_questions')
    question_text = models.TextField()
    location = models.CharField(max_length=100, blank=True)
    keywords = models.TextField(help_text="Keywords separated by commas")
    answer_reference = models.CharField(max_length=200, blank=True)
    active_status = models.CharField(max_length=20, choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Swali la Mkulima'
        verbose_name_plural = 'Maswali ya Wakulima'

    def __str__(self):
        return self.question_text[:80]


class Synonym(models.Model):
    """Maneno mbadala, makosa ya tahajia na lugha ya kawaida"""
    CATEGORIES = [
        ('crop', 'Zao / Crop'),
        ('intent', 'Intent'),
        ('location', 'Eneo / Location'),
        ('input', 'Pembejeo / Input'),
        ('general', 'Jumla / General'),
    ]

    main_word = models.CharField(max_length=100)
    variation = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=CATEGORIES)
    crop = models.ForeignKey(Crop, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['main_word']
        verbose_name = 'Synonym'
        verbose_name_plural = 'Synonyms'
        unique_together = ['main_word', 'variation']

    def __str__(self):
        return f"{self.variation} → {self.main_word}"


class AnswerTemplate(models.Model):
    """Majibu yatakayotumwa kwa mkulima"""
    answer_reference = models.CharField(max_length=200, unique=True)
    intent = models.ForeignKey(Intent, on_delete=models.CASCADE, related_name='answer_templates')
    crop = models.ForeignKey(Crop, on_delete=models.SET_NULL, null=True, blank=True, related_name='answer_templates')
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='answer_templates')
    answer_text_sw = models.TextField(verbose_name="Jibu (Kiswahili)")
    follow_up_question = models.TextField(blank=True)
    caution_note = models.TextField(blank=True)
    active_status = models.CharField(max_length=20, choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['intent', 'crop', 'zone']
        verbose_name = 'Answer Template'
        verbose_name_plural = 'Answer Templates'

    def __str__(self):
        return self.answer_reference
