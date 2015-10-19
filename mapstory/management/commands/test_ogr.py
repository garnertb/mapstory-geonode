import os
import time
from django.core.management.base import BaseCommand
from geonode.contrib.dynamic.postgis import file2pgtable
from mapstory.ogr2ogr import main
from geoserver.catalog import Catalog
from geonode.layers.models import Layer
from django.conf import settings
from geonode.geoserver.helpers import ogc_server_settings
from geonode.geoserver.helpers import gs_slurp
from django.contrib.gis.gdal import DataSource

# ls test_ogr/no_date/*.shp | xargs sudo -u postgres /home/mapstory/.virtualenvs/mapstory/bin/python manage.py test_ogr
# ls test_ogr/*.shp | xargs sudo -u postgres /home/mapstory/.virtualenvs/mapstory/bin/python manage.py test_ogr

def measureTime(a):
    start = time.clock()
    a()
    elapsed = time.clock()
    elapsed = elapsed - start
    print "Time spent in (function name) is: ", elapsed

def createFeatureType(catalog, datastore, name):
    """
    Exposes a PostGIS feature type in geoserver.
    """
    headers = {"Content-type": "application/xml"}
    data = "<featureType><name>{name}</name></featureType>".format(name=name)
    url = datastore.href.replace(".xml", '/featuretypes.xml'.format(name=name))
    headers, response = catalog.http.request(url, "POST ", data, headers)
    return response

class Command(BaseCommand):
    help = 'Runs the OGR tests'

    def add_arguments(self, parser):
        parser.add_argument('file', nargs='+')

    def handle(self, *args, **options):

        cat = Catalog(ogc_server_settings.internal_rest, *ogc_server_settings.credentials)
        store = cat.get_store(ogc_server_settings.DATASTORE, 'geonode')

        for in_file in args:
            name = os.path.split(in_file)[1]
            extension = os.path.splitext(in_file)[1]
            name_no_ext = name.replace(extension, '')

            resource = store.get_resources(name_no_ext)

            if resource:
                cat.delete(resource, recurse=True)


            #ds = DataSource(in_file)


            # clock in the import process

            start = time.clock()
            opts = []

            opts.append('-overwrite')
            opts.append('-skipfailures')

            args = ["", "-f", "PostgreSQL",
                    "PG:dbname=mapstory_data user={0} password={1}".format('mapstory', 'foobar'), in_file] + opts

            # run ogr2ogr
            main(args)

            # expose the featureType in geoserver
            createFeatureType(cat, store, name_no_ext)

            # add to geonode
            gs_slurp(workspace='geonode', store=store.name, filter=name_no_ext)

            # done
            elapsed = time.clock() - start

            try:
                Layer.objects.get(name=name_no_ext).get_absolute_url()
            except:
                print name_no_ext


            print '---------------------------'
            print os.path.split(in_file)[-1], 'in', elapsed
            print Layer.objects.get(name=name_no_ext).get_absolute_url()
            print '---------------------------'
            print

#from geonode.geoserver.helpers import gs_slurp


# def layer_create(request, data=None, template='upload/layer_create.html'):
# print 'layer create'
# if request.method == 'POST':
# feature_type = json.loads(request.POST.get(u'featureType', None))
# headers = {'content-type': 'application/json'}
# data = '{{"featureType":{}}}'.format(json.dumps(feature_type))
# post_request = requests.post(
# 'http://localhost/geoserver/rest/workspaces/geonode/datastores/datastore/featuretypes.json',
# data=data,
# auth=('admin', 'geoserver'),
# headers=headers
# )
#
# # import the layer from geoserver to geonode
# response = gs_slurp(filter=feature_type['name'])
# success = False
# if 'layers' in response and len(response['layers']) == 1 and 'name' in response['layers'][0] and response['layers'][0]['name'] == feature_type['name']:
# success = True
#
# context_dict = {
# "success": success,
# }
# print '---- create layer response: ', post_request.text
#
# else:
# context_dict = {}
#
# return render_to_response(template, RequestContext(request, context_dict))