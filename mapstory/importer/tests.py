import os
import json
import re
from account.models import EmailConfirmation
from django import db
from django.test import TestCase, Client
from django.test.utils import override_settings
from django.conf import settings
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model, authenticate
from mapstory.importer.models import UploadedData, UploadFile
from django.contrib.staticfiles import finders
from geonode.base.models import TopicCategory
from geonode.base.populate_test_data import create_models
from geonode.layers.models import Layer
from geonode.layers.populate_layers_data import create_layer_data
from mapstory.models import Community, DiaryEntry
from django.contrib.gis.gdal import DataSource
from unittest import skip
from csv import DictReader
from mapstory.importer.utils import GDALImport
import time
from mapstory.importer.ogr2ogr import main
from mapstory.importer.utils import create_vrt, configure_time, ensure_defaults, GDALInspector, OGRFieldConverter
from geoserver.catalog import Catalog, FailedRequestError
from geonode.layers.models import Layer
from django.conf import settings
from geonode.geoserver.helpers import ogc_server_settings
from geonode.geoserver.helpers import gs_slurp
User = get_user_model()


class AdminClient(Client):

    def login_as_admin(self, username='admin', password='admin'):
        """
        Convenience method to login admin.
        """
        return self.login(**{'username': username, 'password': password})

    def login_as_non_admin(self, username='non_admin', password='non_admin'):
        """
        Convenience method to login a non-admin.
        """
        return self.login(**{'username': username, 'password': password})

class MapStoryTestMixin(TestCase):

    def assertLoginRequired(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertTrue('login' in response.url)

    def assertHasGoogleAnalytics(self, response):
        self.assertTrue('mapstory/google_analytics.html' in [t.name for t in response.templates])

    def create_user(self, username, password, **kwargs):
        """
        Convenience method for creating users.
        """
        user, created = User.objects.get_or_create(username=username, **kwargs)

        if created:
            user.set_password(password)
            user.save()

        return username, password


class UploaderTests(MapStoryTestMixin):
    """
    Basic checks to make sure pages load, etc.
    """

    def create_datastore(self, connection, catalog):
        settings = connection.settings_dict
        params = {'database': settings['NAME'],
                  'passwd': settings['PASSWORD'],
                  'namespace': 'http://www.geonode.org/',
                  'type': 'PostGIS',
                  'dbtype': 'postgis',
                  'host': settings['HOST'],
                  'user': settings['USER'],
                  'port': settings['PORT'],
                  'enabled': "True"}

        store = catalog.create_datastore(settings['NAME'], workspace=self.workspace)
        store.connection_parameters.update(params)

        try:
            catalog.save(store)
        except FailedRequestError:
            # assuming this is because it already exists
            pass

        return catalog.get_store(settings['NAME'])

    def setUp(self):
        # These tests require geonode to be running on :80!
        self.postgis = db.connections['datastore']
        self.postgis_settings = self.postgis.settings_dict

        self.username, self.password = self.create_user('admin', 'admin', is_superuser=True)
        self.non_admin_username, self.non_admin_password = self.create_user('non_admin', 'non_admin')
        self.cat = Catalog(ogc_server_settings.internal_rest, *ogc_server_settings.credentials)
        self.workspace = 'geonode'
        self.datastore = self.create_datastore(self.postgis, self.cat)

    def tearDown(self):
        """
        Clean up geoserver.
        """
        self.cat.delete(self.datastore, recurse=True)

    def generic_import(self, file, configuration_options=[{'index': 0}]):

        f = file
        filename = os.path.join(os.path.dirname(__file__), 'test_ogr', f)

        res = self.import_file(filename, configuration_options=configuration_options)
        res = res[0]

        layer = res['layers'][0]

        self.assertEqual(layer['status'], 'updated')
        layer = Layer.objects.get(name=layer['name'])
        self.assertEqual(layer.srid, 'EPSG:4326')
        self.assertEqual(layer.store, self.datastore.name)
        self.assertEqual(layer.storeType, 'dataStore')

        if not filename.endswith('zip'):
            self.assertTrue(layer.attributes.count() >= DataSource(filename)[0].num_fields)

        # make sure we have at least one dateTime attribute
        self.assertTrue('xsd:dateTime' or 'xsd:date' in [n.attribute_type for n in layer.attributes.all()])

        return layer

    def test_box_with_year_field(self):
        """
        Tests the import of test_box_with_year_field.
        """

        layer = self.generic_import('boxes_with_year_field.shp', configuration_options=[{'index': 0,
                                                                                         'convert_to_date': ['date']}])
        date_attr = filter(lambda attr: attr.attribute == 'date_as_date', layer.attributes)[0]
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(self.cat.get_layer(layer.name).resource, attribute=date_attr.attribute,)

        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_boxes_with_date(self):
        """
        Tests the import of test_boxes_with_date.
        """

        layer = self.generic_import('boxes_with_date.shp', configuration_options=[{'index': 0,
                                                                                         'convert_to_date': ['date']}])
        date_attr = filter(lambda attr: attr.attribute == 'date_as_date', layer.attributes)[0]
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(self.cat.get_layer(layer.name).resource, attribute=date_attr.attribute,)

        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_boxes_with_date_csv(self):
        """
        Tests a CSV with WKT polygon.
        """

        layer = self.generic_import('boxes_with_date.csv', configuration_options=[{'index': 0,
                                                                                         'convert_to_date': ['date']}])
        date_attr = filter(lambda attr: attr.attribute == 'date_as_date', layer.attributes)[0]
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(self.cat.get_layer(layer.name).resource, attribute=date_attr.attribute,)

        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_boxes_with_iso_date(self):
        """
        Tests the import of test_boxes_with_iso_date.
        """

        layer = self.generic_import('boxes_with_date_iso_date.shp', configuration_options=[{'index': 0,
                                                                                         'convert_to_date': ['date']}])
        date_attr = filter(lambda attr: attr.attribute == 'date_as_date', layer.attributes)[0]
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(self.cat.get_layer(layer.name).resource, attribute=date_attr.attribute,)

        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_boxes_with_date_iso_date_zip(self):
        """
        Tests the import of test_boxes_with_iso_date.
        """

        layer = self.generic_import('boxes_with_date_iso_date.zip', configuration_options=[{'index': 0,
                                                                                         'convert_to_date': ['date']}])
        date_attr = filter(lambda attr: attr.attribute == 'date_as_date', layer.attributes)[0]
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(self.cat.get_layer(layer.name).resource, attribute=date_attr.attribute,)

        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_boxes_with_dates_bc(self):
        """
        Tests the import of test_boxes_with_dates_bc.
        """

        layer = self.generic_import('boxes_with_dates_bc.shp', configuration_options=[{'index': 0,
                                                                                         'convert_to_date': ['date']}])

        date_attr = filter(lambda attr: attr.attribute == 'date_as_date', layer.attributes)[0]
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(self.cat.get_layer(layer.name).resource, attribute=date_attr.attribute,)

        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_point_with_date(self):
        """
        Tests the import of test_boxes_with_dates_bc.
        """

        layer = self.generic_import('point_with_date.geojson', configuration_options=[{'index': 0,
                                                                                         'convert_to_date': ['date']}])

        # OGR will name geojson layers 'ogrgeojson' we rename to the path basename
        self.assertTrue(layer.name.startswith('point_with_date'))

        date_attr = filter(lambda attr: attr.attribute == 'date_as_date', layer.attributes)[0]
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(self.cat.get_layer(layer.name).resource, attribute=date_attr.attribute,)
        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_boxes_with_end_date(self):
        """
        Tests the import of test_boxes_with_end_date.
        This layer has a date and an end date field that are typed correctly.
        """

        layer = self.generic_import('boxes_with_end_date.shp')

        date_attr = filter(lambda attr: attr.attribute == 'date', layer.attributes)[0]
        end_date_attr = filter(lambda attr: attr.attribute == 'enddate', layer.attributes)[0]

        self.assertEqual(date_attr.attribute_type, 'xsd:date')
        self.assertEqual(end_date_attr.attribute_type, 'xsd:date')

        configure_time(self.cat.get_layer(layer.name).resource, attribute=date_attr.attribute,
                       end_attribute=end_date_attr.attribute)

        self.generic_time_check(layer, attribute=date_attr.attribute, end_attribute=end_date_attr.attribute)


    def test_us_states_kml(self):
        """
        Tests the import of us_states_kml.
        This layer has a date and an end date field that are typed correctly.
        """
        # TODO: Support time in kmls.

        layer = self.generic_import('us_states.kml')
        #date_attr = filter(lambda attr: attr.attribute == 'date', layer.attributes)[0]
        #end_date_attr = filter(lambda attr: attr.attribute == 'enddate', layer.attributes)[0]
        #self.assertEqual(date_attr.attribute_type, 'xsd:date')
        #self.assertEqual(end_date_attr.attribute_type, 'xsd:date')

        #configure_time(self.cat.get_layer(layer.name).resource, attribute=date_attr.attribute,
        #               end_attribute=end_date_attr.attribute)

        #self.generic_time_check(layer, attribute=date_attr.attribute, end_attribute=end_date_attr.attribute)

    def test_mojstrovka_gpx(self):
        """
        Tests the import of mojstrovka.gpx.
        This layer has a date and an end date field that are typed correctly.
        """
        layer = self.generic_import('mojstrovka.gpx')
        date_attr = filter(lambda attr: attr.attribute == 'time', layer.attributes)[0]
        self.assertEqual(date_attr.attribute_type, u'xsd:dateTime')
        configure_time(self.cat.get_layer(layer.name).resource, attribute=date_attr.attribute)
        self.generic_time_check(layer, attribute=date_attr.attribute)

    def generic_time_check(self, layer, attribute=None, end_attribute=None):
        """
        Convenience method to run generic tests on time layers.
        """
        self.cat._cache.clear()
        resource = self.cat.get_resource(layer.name, store=layer.store, workspace=self.workspace)

        timeInfo = resource.metadata['time']
        self.assertEqual("LIST", timeInfo.presentation)
        self.assertEqual(True, timeInfo.enabled)
        self.assertEqual(attribute, timeInfo.attribute)
        self.assertEqual(end_attribute, timeInfo.end_attribute)

    def test_us_shootings_csv(self):
        """
        Tests the import of US_shootings.csv.
        """

        filename = 'US_shootings.csv'
        f = os.path.join(os.path.dirname(__file__), 'test_ogr', filename)
        layer = self.generic_import(filename, configuration_options=[{'index': 0, 'convert_to_date': ['Date']}])
        self.assertEqual(layer.name, 'us_shootings')

        date_field = 'date_as_date'
        configure_time(self.cat.get_layer(layer.name).resource, attribute=date_field)
        self.generic_time_check(layer, attribute=date_field)

    def get_layer_names(self, in_file):
        """
        Gets layer names from a data source.
        """
        ds = DataSource(in_file)
        return map(lambda layer: layer.name, ds)

    def test_gdal_import(self):
        filename = 'point_with_date.geojson'
        f = os.path.join(os.path.dirname(__file__), 'test_ogr', filename)
        self.generic_import(filename, configuration_options=[{'index': 0,  'convert_to_date': ['date']}])

    def import_file(self, in_file, configuration_options=[]):
        """
        Imports the file.
        """
        self.assertTrue(os.path.exists(in_file))

        # run ogr2ogr
        gi = GDALImport(in_file)
        layers = gi.handle(configuration_options=configuration_options)

        d = db.connections['datastore'].settings_dict
        connection_string = "PG:dbname='%s' user='%s' password='%s'" % (d['NAME'], d['USER'], d['PASSWORD'])

        #for configuration_option in configuration_options:
        #    for field in configuration_option.get('convert_to_date', []):
        #        with OGRFieldConverter(connection_string) as datasource:
        #            datasource.convert_field(layers[configuration_option.get('index', 0)][0], field)

        output = []
        for layer, layer_config in layers:
            # expose the featureType in geoserver
            self.cat.publish_featuretype(layer, self.datastore, 'EPSG:4326')
            output.append(gs_slurp(workspace='geonode', store=self.datastore.name, filter=layer))

        return output


    @staticmethod
    def createFeatureType(catalog, datastore, name):
        """
        Exposes a PostGIS feature type in geoserver.
        """
        headers = {"Content-type": "application/xml"}
        data = "<featureType><name>{name}</name></featureType>".format(name=name)
        url = datastore.href.replace(".xml", '/featuretypes.xml'.format(name=name))
        headers, response = catalog.http.request(url, "POST ", data, headers)
        return response

    def test_create_vrt(self):
        """
        Tests the create_vrt function.
        """
        f = os.path.join(os.path.dirname(__file__), 'test_ogr', 'US_shootings.csv')

        vrt = create_vrt(f)
        vrt.seek(0)
        output = vrt.read()

        self.assertTrue('name="US_shootings"' in output)
        self.assertTrue('<SrcDataSource>{0}</SrcDataSource>'.format(f) in output)
        self.assertTrue('<GeometryField encoding="PointFromColumns" x="Longitude" y="Latitude" />'.format(f) in output)
        self.assertEqual(os.path.splitext(vrt.name)[1], '.vrt')

    def test_file_add_view(self):
        """
        Tests the file_add_view.
        """
        f = os.path.join(os.path.dirname(__file__), 'test_ogr', 'point_with_date.geojson')
        c = AdminClient()
        c.login_as_non_admin()

        with open(f) as fp:
            response = c.post(reverse('uploads-new'), {'file': fp}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['request'].path, reverse('uploads-list'))
        self.assertTrue(len(response.context['object_list']) == 1)

        upload = response.context['object_list'][0]
        self.assertEqual(upload.user.username, 'non_admin')
        self.assertTrue(upload.uploadlayer_set.all())
        self.assertEqual(upload.state, 'Uploaded')

        uploaded_file = upload.uploadfile_set.first()
        self.assertTrue(os.path.exists(uploaded_file.file.path))

    def test_describe_fields(self):
        """
        Tests the describe fields functionality.
        """
        f = os.path.join(os.path.dirname(__file__), 'test_ogr', 'us_shootings.csv')
        fields = None

        with GDALInspector(f) as f:
            layers = f.describe_fields()

        self.assertTrue(layers[0]['name'], 'us_shootings')
        self.assertEqual([n['name'] for n in layers[0]['fields']], ['Date', 'Shooter', 'Killed',
                                                                                 'Wounded', 'Location', 'City',
                                                                                 'Longitude', 'Latitude'])

    def test_configure_view(self):
        """
        Tests the configuration view.
        """
        f = os.path.join(os.path.dirname(__file__), 'test_ogr', 'point_with_date.geojson')
        c = AdminClient()
        c.login_as_non_admin()

        with open(f) as fp:
            response = c.post(reverse('uploads-new'), {'file': fp}, follow=True)

        upload = response.context['object_list'][0]

        payload = [{'index': 0,
                    'convert_to_date': ['date'],
                    'start_date': 'date',
                    'configureTime': True,
                    'editable': True}]

        response = c.post(reverse('uploads-configure', args=[upload.id]), data=json.dumps(payload),
                          content_type='application/json')
        self.assertTrue(response.status_code, 302)
        layer = Layer.objects.all()[0]
        self.assertEqual(layer.srid, 'EPSG:4326')
        self.assertEqual(layer.store, self.datastore.name)
        self.assertEqual(layer.storeType, 'dataStore')
        self.assertTrue(layer.attributes[1].attribute_type, 'xsd:dateTime')

        lyr = self.cat.get_layer(layer.name)
        self.assertTrue('time' in lyr.resource.metadata)

    def test_configure_view_convert_date(self):
        """
        Tests the configure view with a dataset that needs to be converted to a date.
        """
        f = os.path.join(os.path.dirname(__file__), 'test_ogr', 'US_shootings.csv')
        c = AdminClient()
        c.login_as_non_admin()

        with open(f) as fp:
            response = c.post(reverse('uploads-new'), {'file': fp}, follow=True)

        upload = response.context['object_list'][0]

        payload = [{'index': 0,
                    'convert_to_date': ['Date'],
                    'start_date': 'Date',
                    'configureTime': True,
                    'editable': True}]

        response = c.post(reverse('uploads-configure', args=[upload.id]), data=json.dumps(payload),
                          content_type='application/json')
        self.assertTrue(response.status_code, 302)

        layer = Layer.objects.all()[0]
        self.assertEqual(layer.srid, 'EPSG:4326')
        self.assertEqual(layer.store, self.datastore.name)
        self.assertEqual(layer.storeType, 'dataStore')
        self.assertTrue(layer.attributes[1].attribute_type, 'xsd:dateTime')
        self.assertTrue(layer.attributes.filter(attribute='date_as_date'), 'xsd:dateTime')

        lyr = self.cat.get_layer(layer.name)
        self.assertTrue('time' in lyr.resource.metadata)

    def test_describe_fields_view(self):
        f = os.path.join(os.path.dirname(__file__), 'test_ogr', 'point_with_date.geojson')
        c = AdminClient()
        c.login_as_non_admin()

        with open(f) as fp:
            response = c.post(reverse('uploads-new'), {'file': fp}, follow=True)

        self.assertTrue(response.status_code, 200)

        upload = UploadedData.objects.first()
        response = c.get(reverse('uploads-fields', args=[upload.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response._headers['content-type'][1], 'application/json')

        # just make sure this does not error out
        description = json.loads(response.content)
        self.assertTrue('fields' in description[0])
        self.assertTrue('name' in description[0])


    def test_delete_view(self):
        upload = UploadedData()
        upload.save()

        c = AdminClient()
        response = c.get(reverse('uploads-delete', args=[upload.id]))
        self.assertEqual(200, response.status_code)

        response = c.post(reverse('uploads-delete', args=[upload.id]), follow=True)
        self.assertEqual(200, response.status_code)

        # make sure the object is actually deleted
        with self.assertRaises(UploadedData.DoesNotExist):
            UploadedData.objects.get(id=upload.id)

    def test_list_api(self):
        c = AdminClient()
        response = c.get('/importer-api/data/')
        self.assertEqual(response.status_code, 200)

