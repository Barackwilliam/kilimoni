"""
Majaribio ya kupokea dataset: mazao mapya, mgongano wa ID kati ya mazao,
na ripoti ya uchambuzi.
"""
import glob
import os
import shutil
import tempfile

import openpyxl
from django.contrib.auth.models import User as AuthUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from advisory.models import SoilSuitability
from crops.models import Crop

from . import crops as crop_intake
from .analysis import analyse

ADV = os.path.join(os.path.dirname(__file__), '..', 'advisory', 'fixtures')
SOIL = sorted(glob.glob(os.path.join(ADV, 'MHD-004*.xlsx')))
SUIT = next(p for p in SOIL if 'Suitability' in p)
OTHER_SOIL = [p for p in SOIL if p != SUIT]


def _upload(path, name=None):
    with open(path, 'rb') as fh:
        return SimpleUploadedFile(name or os.path.basename(path), fh.read())


def edit_workbook(src, folder, edits, rename_headers=None, name=None):
    """edits: {sheet: fn(header, row_values) → row_values}; rename_headers: {sheet: {old: new}}."""
    wb = openpyxl.load_workbook(src)
    for sheet, fn in edits.items():
        ws = wb[sheet]
        header = [c.value for c in ws[1]]
        for row in ws.iter_rows(min_row=2):
            if any(c.value not in (None, '') for c in row):
                values = fn(header, [c.value for c in row])
                for c, v in zip(row, values):
                    c.value = v
    for sheet, mapping in (rename_headers or {}).items():
        for c in wb[sheet][1]:
            if c.value in mapping:
                c.value = mapping[c.value]
    dest = os.path.join(folder, name or os.path.basename(src))
    wb.save(dest)
    return dest


def to_crop(crop_name, id_prefix=None):
    """Badilisha jina_la_zao kuwa crop_name (na ID ya kwanza ipewe kiambishi, kama dataset ya zao jipya)."""
    def fn(header, values):
        out = list(values)
        for i, h in enumerate(header):
            if h == 'jina_la_zao':
                out[i] = crop_name
        if id_prefix:
            out[0] = f"{id_prefix}{out[0]}"
        return out
    return fn


class SplitNameTests(TestCase):
    def test_names(self):
        self.assertEqual(crop_intake.split_name('Mahindi (Maize)'), ('Mahindi', 'Maize'))
        self.assertEqual(crop_intake.split_name('Maize'), ('Mahindi', 'Maize'))
        self.assertEqual(crop_intake.split_name('Beans'), ('Maharage', 'Beans'))
        self.assertEqual(crop_intake.split_name('Alizeti'), ('Alizeti', 'Sunflower'))
        self.assertEqual(crop_intake.split_name('Mbuyu'), ('Mbuyu', ''))
        self.assertEqual(crop_intake.guess_group('Alizeti', 'Sunflower'), 'cash_crops')

    def test_english_name_matches_existing_crop(self):
        maize = Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        intake = crop_intake.CropIntake(create=True)
        for name in ('Maize', 'mahindi', 'Mahindi (Maize)', ' MAIZE '):
            self.assertEqual(intake.resolve(name), maize)
        self.assertEqual(intake.missing, [])

    def test_default_does_not_create(self):
        self.assertIsNone(crop_intake.resolve('Alizeti'))
        self.assertFalse(Crop.objects.filter(crop_name_sw='Alizeti').exists())


class NewCropUploadTests(TestCase):
    def setUp(self):
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        AuthUser.objects.create_user('kilimoni', password='x', is_staff=True)
        self.client.login(username='kilimoni', password='x')
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.sunflower = edit_workbook(SUIT, self.tmp, {
            'Soil_Crop_Suitability_Master': to_crop('Alizeti', 'ALZ-'),
            'Crop_Top_Soil_Ranking': to_crop('Alizeti', 'ALZ-')})

    def _preview(self, paths):
        return self.client.post(reverse('rx_preview'), {'files': [_upload(p) for p in paths]})

    def test_preview_lists_new_crop_without_saving_it(self):
        r = self._preview(OTHER_SOIL + [self.sunflower])
        self.assertContains(r, 'Mazao mapya (1)')
        self.assertContains(r, 'value="Alizeti"')
        self.assertContains(r, 'value="Sunflower"')
        self.assertContains(r, 'value="cash_crops" selected')
        self.assertFalse(Crop.objects.filter(crop_name_sw='Alizeti').exists())   # hakiki = rollback
        self.assertEqual(SoilSuitability.objects.count(), 0)
        # jedwali la mazao na moduli linaonyesha Alizeti kana kwamba imehifadhiwa
        cov = r.context['analysis']['coverage']
        self.assertIn('Alizeti', [row['crop'] for row in cov['rows']])

    def test_confirm_with_approval_creates_crop_and_links_data(self):
        self._preview(OTHER_SOIL + [self.sunflower])
        r = self.client.post(reverse('rx_confirm'), {
            'crop_total': '1', 'crop_add_0': '1', 'crop_key_0': 'alizeti', 'crop_sw_0': 'Alizeti',
            'crop_en_0': 'Sunflower', 'crop_group_0': 'cash_crops'}, follow=True)
        self.assertContains(r, 'Mazao mapya yameongezwa: Alizeti')
        crop = Crop.objects.get(crop_name_sw='Alizeti')
        self.assertEqual(crop.crop_group, 'cash_crops')
        self.assertTrue(SoilSuitability.objects.filter(crop=crop).exists())
        # bot inalitambua zao jipya mkulima akilitaja
        from bot.engine import detect_crop
        self.assertEqual(detect_crop('nataka kupanda alizeti'), crop)

    def test_confirm_without_approval_does_not_create(self):
        self._preview(OTHER_SOIL + [self.sunflower])
        r = self.client.post(reverse('rx_confirm'), {'crop_total': '1', 'crop_key_0': 'alizeti',
                                                     'crop_sw_0': 'Alizeti'}, follow=True)
        self.assertContains(r, 'Mazao hayakuongezwa')
        self.assertFalse(Crop.objects.filter(crop_name_sw='Alizeti').exists())
        self.assertTrue(SoilSuitability.objects.filter(crop=None, source_id__startswith='ALZ-').exists())

    def test_same_ids_for_another_crop_are_refused(self):
        """Dataset ya Alizeti ikitumia ID zilezile za Mahindi isiandike juu ya data ya Mahindi."""
        self._preview(SOIL)
        self.client.post(reverse('rx_confirm'))
        maize_rows = SoilSuitability.objects.filter(crop__crop_name_sw='Mahindi').count()
        self.assertGreater(maize_rows, 0)
        clash = edit_workbook(SUIT, self.tmp, {'Soil_Crop_Suitability_Master': to_crop('Alizeti'),
                                               'Crop_Top_Soil_Ranking': to_crop('Alizeti')}, name='MHD-004_clash.xlsx')
        r = self._preview(OTHER_SOIL + [clash])
        self.assertContains(r, 'tayari inatumika kwa Mahindi')
        self.assertNotContains(r, 'Hifadhi data hii')            # makosa mengi → rollback
        self.assertEqual(SoilSuitability.objects.filter(crop__crop_name_sw='Mahindi').count(), maize_rows)


class AnalysisTests(TestCase):
    def setUp(self):
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _book(self, result, needle):
        return next(b for b in result['books'] if needle in b['file'])

    def test_broken_links_are_found(self):
        result = analyse(SOIL)
        texts = [i['text'] + ' ' + ' '.join(i['examples']) for i in self._book(result, 'Suitability')['issues']]
        self.assertTrue(any('SOL-WRB-003' in t and 'hazipo' in t for t in texts), texts)

    def test_renamed_required_column_is_flagged(self):
        master = next(p for p in SOIL if 'Soil_Intelligence_Master' in p)
        renamed = edit_workbook(master, self.tmp, {}, rename_headers={
            'Soil_Master_Registry': {'jina_la_kiswahili': 'jina_kiswahili'}})
        issues = self._book(analyse([renamed]), 'Soil_Intelligence')['issues']
        hit = [i for i in issues if 'jina_la_kiswahili' in i['text']]
        self.assertTrue(hit and hit[0]['level'] == 'high', issues)

    def test_english_farmer_text_is_flagged(self):
        master = next(p for p in SOIL if 'Soil_Intelligence_Master' in p)

        def english(header, values):
            out = list(values)
            out[header.index('ujumbe_wa_mkulima')] = 'Use lime only when the soil test is available for the field.'
            return out
        path = edit_workbook(master, self.tmp, {'Soil_Decision_Rules': english})
        issues = self._book(analyse([path]), 'Soil_Intelligence')['issues']
        self.assertTrue(any('Kiingereza' in i['text'] for i in issues), issues)

    def test_unsupported_workbook_is_analysed_not_rejected(self):
        path = shutil.copy(SUIT, os.path.join(self.tmp, 'MHD-005_Fertilizer_Test.xlsx'))
        book = analyse([path], supported_codes=['MHD-001'])['books'][0]
        self.assertEqual(book['status'], 'Haina moduli ya kanuni bado')
        self.assertGreater(book['data_rows'], 0)

    def test_sheets_used_marks_engine_sheets(self):
        from advisory.importer import import_files
        report = import_files(SOIL, dry_run=True)
        book = self._book(analyse(SOIL, [report]), 'Soil_Intelligence')
        used = {s['name'] for s in book['sheets'] if s['used']}
        self.assertIn('Soil_Master_Registry', used)
        self.assertFalse(any('hakuna injini' in i['text'] for i in book['issues']))
