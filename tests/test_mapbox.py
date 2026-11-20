"""Mapbox contracts with isolated database and mocked HTTP, no stored POIs."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from tests import create_test_app
from app.services import mapbox_service as service
from app.models.health_facility import HealthFacility
from app.extensions import db


def feature(identifier='mapbox.test', **kwargs):
    return dict(type='Feature', geometry={'type':'Point','coordinates':[112.4,-7.1]},
                properties=dict(mapbox_id=identifier,name='RS Uji',context={'country':{'country_code':'ID'}},**kwargs))


class MapboxTests(unittest.TestCase):
    def setUp(self):
        self.app=create_test_app();self.app.config['MAPBOX_PUBLIC_TOKEN']='pk.fixture'
        self.context=self.app.app_context();self.context.push();self.client=self.app.test_client()
        service._requests.clear()

    def tearDown(self):
        db.session.remove();self.context.pop()

    def test_secret_token_never_rendered(self):
        self.app.config['MAPBOX_PUBLIC_TOKEN']='sk.private'
        self.assertFalse(service.public_settings()['configured'])
        self.assertNotIn('sk.private',self.client.get('/').text)

    @patch.object(service,'_request',return_value={'features':[feature()], 'attribution':'Mapbox'})
    def test_search_returns_pois_without_database_mutation(self,request):
        before=db.session.query(HealthFacility).count()
        response=self.client.get('/facilities/mapbox-search?city=Lamongan&facility_type=HOSPITAL')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['count'],1)
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(db.session.query(HealthFacility).count(),before)
        self.assertEqual(request.call_args.args[0],'category/hospital')
        self.assertEqual(request.call_args.args[1]['near'],'Lamongan, Indonesia')

    @patch.object(service,'_request',return_value={'features':[]})
    def test_text_and_nearby_search(self,request):
        service.search(query='Soegiri',city='Lamongan')
        self.assertEqual(request.call_args.args[0],'forward')
        self.assertEqual(request.call_args.args[1]['q'],'Soegiri Lamongan')
        service.search(city='',lat=-7,lng=112)
        self.assertNotIn('near',request.call_args.args[1])
        self.assertEqual(request.call_args.args[1]['proximity'],'112.0,-7.0')

    @patch.object(service,'_request')
    def test_invalid_inputs_do_not_call_api(self,request):
        for query in ['lat=nan&lng=112','lat=91&lng=112','lat=1','facility_type=arbitrary','query='+'x'*151]:
            self.assertEqual(self.client.get('/facilities/mapbox-search?'+query).status_code,400)
        request.assert_not_called()

    def test_normalization_deduplicates_rejects_bad_coordinates_and_foreign_results(self):
        invalid=feature('invalid');invalid['geometry']['coordinates']=[float('nan'),0]
        foreign=feature('foreign');foreign['properties']['context']['country']['country_code']='US'
        self.assertEqual(len(service.normalize([feature(),feature(),invalid,foreign,{'geometry':'bad'}])),1)

    @patch.object(service,'urlopen',side_effect=URLError('contains-sensitive-url'))
    def test_network_failure_is_sanitized(self,request):
        response=self.client.get('/facilities/mapbox-search')
        self.assertEqual(response.status_code,503)
        self.assertNotIn('contains-sensitive-url',response.text)

    @patch.object(service,'urlopen',side_effect=HTTPError('sensitive-url',429,'Limit',{},io.BytesIO()))
    def test_upstream_quota_failure(self,request):
        response=self.client.get('/facilities/mapbox-search')
        self.assertEqual(response.status_code,429)
        self.assertEqual(response.headers['Retry-After'],'60')
        self.assertNotIn('sensitive-url',response.text)

    @patch.object(service,'_request')
    def test_local_rate_limit(self,request):
        import time
        service._requests.extend([time.monotonic()]*45)
        self.assertEqual(self.client.get('/facilities/mapbox-search').status_code,429)
        request.assert_not_called()

    def test_search_ui_appears_only_with_public_token(self):
        self.assertIn('data-mapbox-directory',self.client.get('/').text)
        self.assertNotIn('data-mapbox-directory',self.client.get('/facilities').text)
        self.app.config['MAPBOX_PUBLIC_TOKEN']=''
        self.assertNotIn('data-mapbox-directory',self.client.get('/').text)
