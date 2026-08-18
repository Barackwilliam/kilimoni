"""
CSV Import Module — Mkulima AI Tanzania
Inasaidia ku-upload datasets kupitia Admin Dashboard bila developer
Formats: maize_varieties.csv, maize_answer_templates.csv, maize_synonyms.csv n.k.
"""
import csv
import io
import logging
from crops.models import (
    Crop, Zone, Intent, SeedVariety, AnswerTemplate,
    Synonym, FarmerQuestion, CropProfile, LocationMapping
)

logger = logging.getLogger(__name__)


def parse_csv_file(file_object) -> list:
    """Parse uploaded CSV file"""
    try:
        content = file_object.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8-sig')  # Handle BOM
        reader = csv.DictReader(io.StringIO(content))
        return list(reader)
    except Exception as e:
        logger.error(f"CSV parse error: {e}")
        raise ValueError(f"Hitilafu ya kusoma CSV: {e}")


def import_varieties(rows: list) -> dict:
    """
    Import seed_varieties
    Columns: variety_name, crop_name_sw, zone_name, maturity_class,
             maturity_days_min, maturity_days_max, drought_tolerance,
             seed_source, verification_status, notes
    """
    created, updated, errors = 0, 0, []
    for i, row in enumerate(rows, 1):
        try:
            crop_name = row.get('crop_name_sw', '').strip()
            variety_name = row.get('variety_name', '').strip()
            if not crop_name or not variety_name:
                errors.append(f"Mstari {i}: crop_name_sw au variety_name haipo")
                continue

            crop = Crop.objects.filter(crop_name_sw__iexact=crop_name).first()
            if not crop:
                errors.append(f"Mstari {i}: Zao '{crop_name}' halijapatikana")
                continue

            zone = None
            zone_name = row.get('zone_name', '').strip()
            if zone_name:
                zone = Zone.objects.filter(zone_name__iexact=zone_name).first()

            defaults = {
                'maturity_class': row.get('maturity_class', 'medium').strip(),
                'drought_tolerance': row.get('drought_tolerance', '').strip(),
                'seed_source': row.get('seed_source', '').strip(),
                'notes': row.get('notes', '').strip(),
                'verification_status': row.get('verification_status', 'pending').strip(),
                'recommended_zone': zone,
            }
            try:
                defaults['maturity_days_min'] = int(row.get('maturity_days_min', 0)) or None
            except (ValueError, TypeError):
                defaults['maturity_days_min'] = None
            try:
                defaults['maturity_days_max'] = int(row.get('maturity_days_max', 0)) or None
            except (ValueError, TypeError):
                defaults['maturity_days_max'] = None

            obj, was_created = SeedVariety.objects.update_or_create(
                crop=crop, variety_name=variety_name, defaults=defaults
            )
            if was_created:
                created += 1
            else:
                updated += 1
        except Exception as e:
            errors.append(f"Mstari {i}: {e}")

    return {'created': created, 'updated': updated, 'errors': errors}


def import_answer_templates(rows: list) -> dict:
    """
    Import answer_templates
    Columns: answer_reference, intent_name, crop_name_sw, zone_name,
             answer_text_sw, follow_up_question, caution_note, active_status
    """
    created, updated, errors = 0, 0, []
    for i, row in enumerate(rows, 1):
        try:
            ref = row.get('answer_reference', '').strip()
            intent_name = row.get('intent_name', '').strip()
            if not ref or not intent_name:
                errors.append(f"Mstari {i}: answer_reference au intent_name haipo")
                continue

            intent = Intent.objects.filter(intent_name__iexact=intent_name).first()
            if not intent:
                errors.append(f"Mstari {i}: Intent '{intent_name}' haijapatikana")
                continue

            crop = None
            crop_name = row.get('crop_name_sw', '').strip()
            if crop_name:
                crop = Crop.objects.filter(crop_name_sw__iexact=crop_name).first()

            zone = None
            zone_name = row.get('zone_name', '').strip()
            if zone_name:
                zone = Zone.objects.filter(zone_name__iexact=zone_name).first()

            defaults = {
                'intent': intent,
                'crop': crop,
                'zone': zone,
                'answer_text_sw': row.get('answer_text_sw', '').strip(),
                'follow_up_question': row.get('follow_up_question', '').strip(),
                'caution_note': row.get('caution_note', '').strip(),
                'active_status': row.get('active_status', 'active').strip(),
            }

            obj, was_created = AnswerTemplate.objects.update_or_create(
                answer_reference=ref, defaults=defaults
            )
            if was_created:
                created += 1
            else:
                updated += 1
        except Exception as e:
            errors.append(f"Mstari {i}: {e}")

    return {'created': created, 'updated': updated, 'errors': errors}


def import_synonyms(rows: list) -> dict:
    """
    Import synonyms
    Columns: main_word, variation, category, crop_name_sw
    """
    created, updated, errors = 0, 0, []
    for i, row in enumerate(rows, 1):
        try:
            main_word = row.get('main_word', '').strip().lower()
            variation = row.get('variation', '').strip().lower()
            if not main_word or not variation:
                errors.append(f"Mstari {i}: main_word au variation haipo")
                continue

            crop = None
            crop_name = row.get('crop_name_sw', '').strip()
            if crop_name:
                crop = Crop.objects.filter(crop_name_sw__iexact=crop_name).first()

            obj, was_created = Synonym.objects.update_or_create(
                main_word=main_word, variation=variation,
                defaults={
                    'category': row.get('category', 'general').strip(),
                    'crop': crop,
                }
            )
            if was_created:
                created += 1
            else:
                updated += 1
        except Exception as e:
            errors.append(f"Mstari {i}: {e}")

    return {'created': created, 'updated': updated, 'errors': errors}


def import_farmer_questions(rows: list) -> dict:
    """
    Import farmer_questions
    Columns: question_text, intent_name, crop_name_sw, location, keywords, answer_reference
    """
    created, updated, errors = 0, 0, []
    for i, row in enumerate(rows, 1):
        try:
            question_text = row.get('question_text', '').strip()
            intent_name = row.get('intent_name', '').strip()
            if not question_text or not intent_name:
                errors.append(f"Mstari {i}: question_text au intent_name haipo")
                continue

            intent = Intent.objects.filter(intent_name__iexact=intent_name).first()
            if not intent:
                errors.append(f"Mstari {i}: Intent '{intent_name}' haijapatikana")
                continue

            crop = None
            crop_name = row.get('crop_name_sw', '').strip()
            if crop_name:
                crop = Crop.objects.filter(crop_name_sw__iexact=crop_name).first()

            obj, was_created = FarmerQuestion.objects.update_or_create(
                question_text=question_text,
                defaults={
                    'intent': intent, 'crop': crop,
                    'location': row.get('location', '').strip(),
                    'keywords': row.get('keywords', '').strip(),
                    'answer_reference': row.get('answer_reference', '').strip(),
                    'active_status': 'active',
                }
            )
            if was_created:
                created += 1
            else:
                updated += 1
        except Exception as e:
            errors.append(f"Mstari {i}: {e}")

    return {'created': created, 'updated': updated, 'errors': errors}


def import_location_mapping(rows: list) -> dict:
    """
    Import location_mapping
    Columns: region_name, district_name, zone_name
    """
    created, updated, errors = 0, 0, []
    for i, row in enumerate(rows, 1):
        try:
            region_name = row.get('region_name', '').strip()
            zone_name = row.get('zone_name', '').strip()
            if not region_name or not zone_name:
                errors.append(f"Mstari {i}: region_name au zone_name haipo")
                continue

            zone = Zone.objects.filter(zone_name__iexact=zone_name).first()
            if not zone:
                errors.append(f"Mstari {i}: Zone '{zone_name}' haijapatikana")
                continue

            district_name = row.get('district_name', '').strip()
            obj, was_created = LocationMapping.objects.update_or_create(
                region_name=region_name, district_name=district_name,
                defaults={'zone': zone}
            )
            if was_created:
                created += 1
            else:
                updated += 1
        except Exception as e:
            errors.append(f"Mstari {i}: {e}")

    return {'created': created, 'updated': updated, 'errors': errors}


# ── Import dispatcher ──────────────────────────────────
IMPORT_TYPES = {
    'varieties': ('Aina za Mbegu', import_varieties),
    'answer_templates': ('Answer Templates', import_answer_templates),
    'synonyms': ('Synonyms', import_synonyms),
    'farmer_questions': ('Maswali ya Wakulima', import_farmer_questions),
    'location_mapping': ('Location Mapping', import_location_mapping),
}


def run_import(import_type: str, file_object) -> dict:
    """Main import function inayoitwa kutoka view"""
    if import_type not in IMPORT_TYPES:
        return {'error': f"Import type '{import_type}' haijulikani"}

    label, import_fn = IMPORT_TYPES[import_type]
    try:
        rows = parse_csv_file(file_object)
        if not rows:
            return {'error': 'CSV file iko tupu au haina data'}
        result = import_fn(rows)
        result['label'] = label
        result['total_rows'] = len(rows)
        return result
    except Exception as e:
        return {'error': str(e)}
