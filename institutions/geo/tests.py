import json

from django.core.urlresolvers import reverse
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase
from mock import Mock, patch

from geo.management.commands.load_geos_from import Command as LoadGeos
from geo.management.commands.precache_geos import Command as Precache
from geo.models import Geo


class ViewTest(TestCase):
    fixtures = ['many_tracts', 'test_counties']

    def test_tract_tiles(self):
        # lat/lon roughly: 0 to 0.17
        resp = self.client.get(reverse(
            'geo:tiles',
            kwargs={'zoom': 11, 'xtile': 1024, 'ytile': 1024}),
            data={'geo_types': '3'})
        resp = json.loads(resp.content)
        self.assertEqual(len(resp['features']),
                         # Doesn't grab the negative tract
                         3)

        # lat/lon roughly: -4 to -3.8
        resp = self.client.get(reverse(
            'geo:tiles',
            kwargs={'zoom': 11, 'xtile': 1001, 'ytile': 1046}),
            data={'geo_types': '3'})
        resp = json.loads(resp.content)
        self.assertEqual(len(resp['features']), 1)

    def test_county_tiles(self):
        # lat/lon roughly: 3.8 to 4
        resp = self.client.get(reverse(
            'geo:tiles',
            kwargs={'zoom': 11, 'xtile': 1046, 'ytile': 1001}),
            data={'geo_types': '2'})
        resp = json.loads(resp.content)
        self.assertEqual(len(resp['features']), 1)
        self.assertEqual(resp['features'][0]['properties']['name'],
                         'Positive County')

        # lat/lon roughly: -4 to -3.8
        resp = self.client.get(reverse(
            'geo:tiles',
            kwargs={'zoom': 11, 'xtile': 1001, 'ytile': 1046}),
            data={'geo_types': '2'})
        resp = json.loads(resp.content)
        self.assertEqual(len(resp['features']), 1)
        self.assertEqual(resp['features'][0]['properties']['name'],
                         'Negative County')

        # lat/lon roughly: -3.1 to -2.9; Testing that the centroid is checked
        resp = self.client.get(reverse(
            'geo:tiles',
            kwargs={'zoom': 11, 'xtile': 1006, 'ytile': 1041}),
            data={'geo_types': '2'})
        resp = json.loads(resp.content)
        self.assertEqual(len(resp['features']), 1)
        self.assertEqual(resp['features'][0]['properties']['name'],
                         'Negative County')

    def test_tile_limits(self):
        # Multiple zoom levels containing 0, 0
        for z in range(1, 9):
            x = 2**(z - 1)
            resp = self.client.get(
                reverse('geo:tiles',
                        kwargs={'zoom': z, 'xtile': x, 'ytile': x}))
            resp = json.loads(resp.content)
            self.assertEqual(len(resp['features']), 0)
        for z in range(9, 16):
            x = 2**(z - 1)
            resp = self.client.get(
                reverse('geo:tiles',
                        kwargs={'zoom': z, 'xtile': x, 'ytile': x}))
            resp = json.loads(resp.content)
            self.assertEqual(len(resp['features']), 3)

    @patch('geo.views.SearchQuerySet')
    def test_search_name(self, SQS):
        SQS = SQS.return_value.models.return_value.load_all.return_value
        result = Mock()
        result.object.geoid = '11111'
        result.object.geo_type = 1
        result.object.name = 'MSA 1'
        result.object.centlat = 45
        result.object.centlon = 52
        SQS.filter.return_value = [result]
        resp = self.client.get(reverse('geo:search'), {'q': 'Chicago'})
        self.assertTrue('Chicago' in str(SQS.filter.call_args))
        self.assertTrue('content' in str(SQS.filter.call_args))
        self.assertFalse('text_auto' in str(SQS.filter.call_args))
        resp = json.loads(resp.content)
        self.assertEqual(1, len(resp['geos']))
        geo = resp['geos'][0]
        self.assertEqual('11111', geo['geoid'])
        self.assertEqual('MSA 1', geo['name'])
        self.assertEqual(1, geo['geo_type'])
        self.assertEqual(45, geo['centlat'])
        self.assertEqual(52, geo['centlon'])

    @patch('geo.views.SearchQuerySet')
    def test_search_autocomplete(self, SQS):
        SQS = SQS.return_value.models.return_value.load_all.return_value
        SQS.filter.return_value = [Mock()]
        self.client.get(reverse('geo:search'), {'q': 'Chicago', 'auto': '1'})
        self.assertTrue('Chicago' in str(SQS.filter.call_args))
        self.assertFalse('content' in str(SQS.filter.call_args))
        self.assertTrue('text_auto' in str(SQS.filter.call_args))


class PrecacheTest(TestCase):
    def setUp(self):
        self.original_urls = Precache.urls

    def tearDown(self):
        Precache.urls = self.original_urls

    @patch('geo.management.commands.precache_geos.Client')
    def test_handle_with_args(self, client):
        Precache.urls['geo:tiles'] = range(3, 6)
        Precache().handle('3', '5')
        self.assertEqual(3, client.return_value.get.call_count)

    @patch('geo.management.commands.precache_geos.Client')
    def test_handle_no_args(self, client):
        Precache.urls['geo:tiles'] = range(3, 6)
        Precache().handle()
        self.assertEqual(22, client.return_value.get.call_count)


class LoadGeosFromTest(TestCase):
    def test_census_tract(self):
        row = ('1122233333', 'Tract 33333', '11', '222', '33333', '-45',
               '45', Polygon(((0, 0), (0, 2), (-1, 2), (0, 0))))
        field_names = ('GEOID', 'NAME', 'STATEFP', 'COUNTYFP', 'TRACTCE',
                       'INTPTLAT', 'INTPTLON')
        command = LoadGeos()
        geo = command.process_row(row, field_names)

        self.assertEqual('1122233333', geo.geoid)
        self.assertEqual(Geo.TRACT_TYPE, geo.geo_type)
        self.assertEqual('Tract 33333', geo.name)
        self.assertEqual('11', geo.state)
        self.assertEqual('222', geo.county)
        self.assertEqual('33333', geo.tract)
        self.assertEqual(None, geo.csa)
        self.assertEqual(None, geo.cbsa)
        self.assertEqual((-1, 0), (geo.minlon, geo.maxlon))
        self.assertEqual((0, 2), (geo.minlat, geo.maxlat))
        self.assertEqual(-45, geo.centlat)
        self.assertEqual(45, geo.centlon)

    def test_county(self):
        poly1 = Polygon(((0, 0), (0, 2), (-1, 2), (0, 0)))
        poly2 = Polygon(((-4, -2), (-6, -1), (-2, -2), (-4, -2)))
        row = ('11222', 'Some County', '11', '222', '-45', '45',
               MultiPolygon(poly1, poly2))
        field_names = ('GEOID', 'NAME', 'STATEFP', 'COUNTYFP', 'INTPTLAT',
                       'INTPTLON')
        command = LoadGeos()
        geo = command.process_row(row, field_names)

        self.assertEqual('11222', geo.geoid)
        self.assertEqual(Geo.COUNTY_TYPE, geo.geo_type)
        self.assertEqual('Some County', geo.name)
        self.assertEqual('11', geo.state)
        self.assertEqual('222', geo.county)
        self.assertEqual(None, geo.tract)
        self.assertEqual(None, geo.csa)
        self.assertEqual(None, geo.cbsa)
        self.assertEqual((-6, 0), (geo.minlon, geo.maxlon))
        self.assertEqual((-2, 2), (geo.minlat, geo.maxlat))
        self.assertEqual(-45, geo.centlat)
        self.assertEqual(45, geo.centlon)

    def test_metro(self):
        row = ('12345', 'Big City', '090', '12345', 'M1', '-45', '45',
               Polygon(((0, 0), (0, 2), (-1, 2), (0, 0))))
        field_names = ('GEOID', 'NAME', 'CSAFP', 'CBSAFP', 'LSAD', 'INTPTLAT',
                       'INTPTLON')
        command = LoadGeos()
        geo = command.process_row(row, field_names)

        self.assertEqual('12345', geo.geoid)
        self.assertEqual(Geo.METRO_TYPE, geo.geo_type)
        self.assertEqual('Big City', geo.name)
        self.assertEqual(None, geo.state)
        self.assertEqual(None, geo.county)
        self.assertEqual(None, geo.tract)
        self.assertEqual('090', geo.csa)
        self.assertEqual('12345', geo.cbsa)

    def test_micro(self):
        row = ('12345', 'Small Town', '', '12345', 'M2', '-45', '45',
               Polygon(((0, 0), (0, 2), (-1, 2), (0, 0))))
        field_names = ('GEOID', 'NAME', 'CSAFP', 'CBSAFP', 'LSAD', 'INTPTLAT',
                       'INTPTLON')
        command = LoadGeos()
        geo = command.process_row(row, field_names)

        self.assertEqual('12345', geo.geoid)
        self.assertEqual(Geo.MICRO_TYPE, geo.geo_type)
        self.assertEqual('Small Town', geo.name)
        self.assertEqual(None, geo.state)
        self.assertEqual(None, geo.county)
        self.assertEqual(None, geo.tract)
        self.assertEqual(None, geo.csa)
        self.assertEqual('12345', geo.cbsa)
