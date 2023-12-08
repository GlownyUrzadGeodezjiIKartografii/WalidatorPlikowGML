# -*- coding: utf-8 -*-
"""
/***************************************************************************
 walidatorPlikowGML
                                 A QGIS plugin
 Walidator plików GML baz BDOT10k, PRNG, GESUT, EGiB, BDOT500
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2022-12-23
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Marcin Lebiecki - Główny Urząd Geodezji i Kartografii
        email                : marcin.lebiecki@gugik.gov.pl
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.core import *
from qgis import processing
import pathlib


def findDuplicates(layer):
    duplicates = []
    unique = []
    isFirstUnique = True
    for feature in layer.getFeatures():
        isDuplicate = False
        if isFirstUnique:
            unique.append(feature)
            isFirstUnique = False
        else:
            for obj in unique:
                if obj.geometry().isGeosEqual(feature.geometry()):
                    isDuplicate = True
                    break
            if isDuplicate:
                duplicates.append(obj)
            else:
                unique.append(feature)
    return duplicates


def validateGeometry(layer):
    obiektyZbledami = []
    wynik = processing.run("qgis:checkvalidity", {
        'INPUT_LAYER': layer,
        'METHOD': 1,
        'INVALID_OUTPUT': 'TEMPORARY_OUTPUT'
    })
    layer = wynik['INVALID_OUTPUT']
    for obj in layer.getFeatures():
        punkt_początkowy = obj.geometry().asPolyline()[0]
        punkt_końcowy = obj.geometry().asPolyline()[-1]
        if punkt_początkowy != punkt_końcowy or obj['_errors'].count("segmenty") > 1:
            obiektyZbledami.append(obj)
    return obiektyZbledami


def grniacePowiatow():
    mainPath = pathlib.Path(QgsApplication.qgisSettingsDirPath())/pathlib.Path("python/plugins/Walidator_plikow_gml/")
    granicePowiatowPath = str(mainPath) + '/Dane/granice_powiatow/powiaty.shp'
    granicePowiatow_A = QgsVectorLayer(granicePowiatowPath, 'GranicePowiatow', 'ogr')
    
    # rozbicie multipoligon na poligony
    pojedynczeGranice = processing.run("native:multiparttosingleparts", {
        'INPUT': granicePowiatow_A,
        'OUTPUT': 'memory:'
    })
    
    # zamiana typu geometrii z poligonu na linię
    granicePowiatow_L = processing.run("native:polygonstolines", {
        'INPUT': pojedynczeGranice['OUTPUT'],
        'OUTPUT': 'memory:'
    })
    return granicePowiatow_L


def czyPrzecinaGranicePowiatuDlugoscPonizej50m(layer):
    obiektyZbledami = []
    granicePowiatow_L = grniacePowiatow()
    
    for obj in layer.getFeatures():
        if obj.geometry().length() < 50:
            czyPrzecina = False
            for granica in granicePowiatow_L['OUTPUT'].getFeatures():
                if obj.geometry().intersects(granica.geometry()) or obj.geometry().touch(granica.geometry()):
                    czyPrzecina = True
            if not czyPrzecina:
                obiektyZbledami.append(obj)
    return obiektyZbledami


def czyObiektyWewnatrzPowiatu(layer, teryt):
    obiektyZbledami = []
    # mainPath = pathlib.Path(QgsApplication.qgisSettingsDirPath())/pathlib.Path("python/plugins/Walidator_plikow_gml/")
    # granicePowiatowPath = str(mainPath) + '/Dane/granice_powiatow/powiaty.shp'
    # granicePowiatow_A = QgsVectorLayer(granicePowiatowPath, 'GranicePowiatow', 'ogr')
    # request = QgsFeatureRequest(QgsExpression("jpt_kod_je = \'" + teryt + "\'"))
    # requestFeatures = granicePowiatow_A.getFeatures(request)
    # for requestFeature in requestFeatures:
    #     granicaPowiatu = requestFeature
    #     break
    # for obj in layer.getFeatures():
    #     if not granicaPowiatu.geometry().contains(obj.geometry()):
    #         obiektyZbledami.append(obj)
    return obiektyZbledami


def czyOdleglosciMiedzyPoziomicami2m_wersja1(layer):
    obiektyZbledami = []
    spatial_index = QgsSpatialIndex(layer.getFeatures())
    
    for obj1 in layer.getFeatures():
        for obj2 in layer.getFeatures():
            if obj1.id() != obj2.id() and not obj1 in obiektyZbledami and obj1.geometry().distance(obj2.geometry()) < 2 :
                obiektyZbledami.append(obj1)
                break
    return obiektyZbledami


def czyOdleglosciMiedzyPoziomicami2m(layer):
    obiekty_z_bledami = []
    spatial_index = QgsSpatialIndex(layer.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
    for obj1 in layer.getFeatures():
        nearestNeighbors = spatial_index.nearestNeighbor(obj1.geometry(), 2, 0)
        for nn in nearestNeighbors:
            if obj1.id() != nn:
                for obj2 in layer.getFeatures():
                    if nn == obj2.id() and not obj1 in obiekty_z_bledami and obj1.geometry().distance(obj2.geometry()) < 2 and \
                        obj1.geometry().distance(obj2.geometry()) > 0:
                        obiekty_z_bledami.append(obj1)
                        break
    return obiekty_z_bledami


def nadmiernaSegmentacja(layer):
    obiekty_z_bledami = []
    spatial_index = QgsSpatialIndex(layer.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
    for obj1 in layer.getFeatures():
        nearestNeighbors = spatial_index.nearestNeighbor(obj1.geometry(), 2, 0)
        for nn in nearestNeighbors:
            if obj1.id() != nn:
                for obj2 in layer.getFeatures():
                    atrybuty1 = obj1.attributes()[2:]
                    atrybuty2 = obj2.attributes()[2:]
                    if nn == obj2.id() and not obj1 in obiekty_z_bledami and obj1.geometry().distance(obj2.geometry()) < 0.01 and \
                        atrybuty1 == atrybuty2 and not obj1.geometry().equals(obj2.geometry()):
                        obiekty_z_bledami.append(obj1)
                        break
    return obiekty_z_bledami


def przewerteksowanie(layer):
    obiekty_z_bledami = []
    for obj1 in layer.getFeatures():
        geom = obj1.geometry()
        liczbaWerteksów = len(geom.asPolyline())
        if liczbaWerteksów > 2:
            for i in range(0, liczbaWerteksów):
                if i > 0 and i < liczbaWerteksów:
                    odcinek_linii = QgsLineString()
                    odcinek_linii.addVertex(geom.vertexAt(i-1))
                    odcinek_linii.addVertex(geom.vertexAt(i+1))
                    geom1 = QgsGeometry(odcinek_linii)
                    d = geom1.distance(QgsGeometry(geom.vertexAt(i)))
                    if d < 0.05:
                        obiekty_z_bledami.append(obj1)
                        return obiekty_z_bledami
    return obiekty_z_bledami