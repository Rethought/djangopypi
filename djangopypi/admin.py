from django.conf import settings
from django.contrib import admin

from djangopypi.models import *

class ReleaseAdmin(admin.ModelAdmin):
    list_display = ('package', 'version', 'hidden', 'created')

admin.site.register(Package)
admin.site.register(Release, ReleaseAdmin)
admin.site.register(Classifier)
admin.site.register(Distribution)
admin.site.register(Review)

if getattr(settings,'DJANGOPYPI_MIRRORING', False):
    admin.site.register(MasterIndex)
    admin.site.register(MirrorLog)
