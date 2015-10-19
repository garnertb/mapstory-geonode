from django.conf.urls import patterns, url, include
from .views import FileAddView, UploadListView, ConfigureImport, UploadDeleteView, UploadDescribeFields
from tastypie.api import Api
from .api import UploadedDataResource


importer_api = Api(api_name='importer-api')
importer_api.register(UploadedDataResource())

urlpatterns = patterns("",
    url(r'^uploads/new$', FileAddView.as_view(), name='uploads-new'),
    url(r'^uploads/?$', UploadListView.as_view(), name='uploads-list'),
    url(r'^uploads/configure/(?P<pk>\d+)/?$', ConfigureImport.as_view(), name='uploads-configure'),
    url(r'^uploads/delete/(?P<pk>\d+)/?$', UploadDeleteView.as_view(), name='uploads-delete'),
    url(r'^uploads/fields/(?P<pk>\d+)/?$', UploadDescribeFields.as_view(), name='uploads-fields'),
    url(r'', include(importer_api.urls)),
)
