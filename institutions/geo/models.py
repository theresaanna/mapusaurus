import json

from django.contrib.gis.db import models


class StateCensusTract(models.Model):
    """
        This model represents the shapefile for census tracts per state. This
        model is auto-generated using the ogrinspect Django command.
    """

    statefp = models.CharField(max_length=2, db_index=True)
    countyfp = models.CharField(max_length=3)
    tractce = models.CharField(max_length=6)
    geoid = models.CharField(max_length=11, unique=True)
    name = models.CharField(max_length=7)
    namelsad = models.CharField(max_length=20)
    mtfcc = models.CharField(max_length=5)
    funcstat = models.CharField(max_length=1)
    aland = models.FloatField()
    awater = models.FloatField()
    intptlat = models.CharField(max_length=11)
    intptlon = models.CharField(max_length=12)
    geom = models.MultiPolygonField(srid=4269)

    minlat = models.FloatField(db_index=True)
    maxlat = models.FloatField(db_index=True)
    minlon = models.FloatField(db_index=True)
    maxlon = models.FloatField(db_index=True)
    geojson = models.TextField()

    objects = models.GeoManager()

    class Meta:
        index_together = [("statefp", "countyfp"),
                          ("minlat", "minlon"),
                          ("minlat", "maxlon"),
                          ("maxlat", "minlon"),
                          ("maxlat", "maxlon")]

    def __str__(self):
        return '%s (county: %s, state: %s)' % (
            self.namelsad, self.countyfp, self.statefp)

    def auto_fields(self):
        """Populate the min and max lat/lon based on this object's geometry;
        also pre-compute a geojson representation for this model"""
        lons, lats = zip(*[pt for polygon in self.geom.coords
                           for line in polygon
                           for pt in line])
        self.minlat = min(lats)
        self.maxlat = max(lats)
        self.minlon = min(lons)
        self.maxlon = max(lons)

        # geometry is a placeholder, as we'll be inserting a pre-serialized
        # json string
        geojson = {"type": "Feature", "geometry": "$_$"}
        geojson['properties'] = {
            'statefp': self.statefp,
            'countyfp': self.countyfp,
            'tractce': self.tractce,
            'geoid': self.geoid,
            'name': self.name,
            'namelsad': self.namelsad,
            'aland': self.aland,
            'awater': self.awater,
            # Convert to floats now to avoid it client-side (JS)
            'intptlat': float(self.intptlat),
            'intptlon': float(self.intptlon),
            'minlat': self.minlat,
            'maxlat': self.maxlat,
            'minlon': self.minlon,
            'maxlon': self.maxlon
        }
        geojson = json.dumps(geojson)
        geojson = geojson.replace(
            '"$_$"',
            self.geom.simplify(preserve_topology=True).geojson)
        self.geojson = geojson

    def save(self, *args, **kwargs):
        self.auto_fields()
        super(StateCensusTract, self).save(*args, **kwargs)


# Auto-generated `LayerMapping` dictionary for CensusTract model
censustract_mapping = {
    'statefp': 'STATEFP',
    'countyfp': 'COUNTYFP',
    'tractce': 'TRACTCE',
    'geoid': 'GEOID',
    'name': 'NAME',
    'namelsad': 'NAMELSAD',
    'mtfcc': 'MTFCC',
    'funcstat': 'FUNCSTAT',
    'aland': 'ALAND',
    'awater': 'AWATER',
    'intptlat': 'INTPTLAT',
    'intptlon': 'INTPTLON',
    'geom': 'MULTIPOLYGON',
}


class Geo(models.Model):
    STATE_TYPE, COUNTY_TYPE, TRACT_TYPE = range(1, 4)
    TYPES = [(STATE_TYPE, 'State'), (COUNTY_TYPE, 'County'),
             (TRACT_TYPE, 'Census Tract')]

    geoid = models.CharField(max_length=20, primary_key=True)
    geo_type = models.PositiveIntegerField(choices=TYPES)
    name = models.CharField(max_length=50)

    state = models.CharField(max_length=2)
    county = models.CharField(max_length=3, null=True)
    tract = models.CharField(max_length=6, null=True)

    geom = models.MultiPolygonField(srid=4269)

    minlat = models.FloatField()
    maxlat = models.FloatField()
    minlon = models.FloatField()
    maxlon = models.FloatField()
    centlat = models.FloatField()
    centlon = models.FloatField()

    objects = models.GeoManager()

    def as_geojson(self):
        # geometry is a placeholder, as we'll be inserting a pre-serialized
        # json string
        geojson = {"type": "Feature", "geometry": "$_$"}
        geojson['properties'] = {
            'geoid': self.geoid,
            'geoType': Geo.TYPES[self.geo_type - 1],    # 1-indexed
            'name': self.name,
            'state': self.state,
            'county': self.county,
            'tract': self.tract,
            'minlat': self.minlat,
            'maxlat': self.maxlat,
            'minlon': self.minlon,
            'maxlon': self.maxlon,
            'centlat': self.centlat,
            'centlon': self.centlon
        }
        geojson = json.dumps(geojson)
        geojson = geojson.replace(
            '"$_$"',
            self.geom.simplify(preserve_topology=True).geojson)
        return geojson
