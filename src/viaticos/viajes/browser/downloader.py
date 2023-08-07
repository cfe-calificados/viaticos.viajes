# -*- coding: utf-8 -*-
from Products.Five.browser import BrowserView
from plone import api
from plone.namedfile.file import NamedBlobFile as BlobFile
from plone.namedfile.utils import set_headers
from plone.namedfile.utils import stream_data
from Products.CMFCore.utils import getToolByName
from hierarchy import Coordinaciones
from datetime import datetime 
import pytz


class ComprobacionesDownloader(BrowserView):

    def __init__(self, context, request):
        self.context = context
        self.request = request


    def __call__(self):
        return self.downloadFile()
    

    def get_row(self, comprobacion):
        """
        comprobacion: transformación de un objeto de comprobación a cadena para csv.
        POR TERMINAR
        """
        hotel = 0
        avion = 0
        otros = 0
        comidas = 0
        monto = 0
        fecha_comprobacion = ""
        fecha_finanzas = ""
        for o in comprobacion.grupo_comprobacion:
            if 7 == o['clave']:
                hotel += o['importe']
            elif 2 == o['clave']:
                avion += o['importe']
            elif 8 == o['clave']:
                comidas += o['importe']
            else:
                otros+= o['importe']
            monto += o['aprobado']
            #Fecha de comprobacion y finanzas
        for w in comprobacion.workflow_history['comprobacion_workflow']:
            if w['action'] == 'guardar':
                if fecha_comprobacion == "":
                    fecha_comprobacion = w['time']
                elif w['time'] > fecha_comprobacion:
                    fecha_comprobacion = w['time']
            if w['action'] == 'enviar_a_implant':
                if fecha_finanzas == "":
                    fecha_finanzas = w['time']
                elif w['time'] > fecha_finanzas:
                    fecha_finanzas = w['time']
        mexico = pytz.timezone("America/Mexico_City")
        if fecha_comprobacion != "":
            fecha_comprobacion_m = mexico.localize(fecha_comprobacion.utcdatetime()).date()
        else:
            fecha_comprobacion_m = ""
        if fecha_finanzas != "":
            fecha_finanzas_m = mexico.localize(fecha_finanzas.utcdatetime()).date()
        else:
            fecha_finanzas_m = ""

        #Informacón del viaje
        viaje = comprobacion.relacion.to_object
        lugar = '\"' + viaje.ciudad +  ", " + viaje.estado + '\"'
        fecha_salida = viaje.fecha_salida
        fecha_regreso = viaje.fecha_regreso
        colaborador = viaje.getOwner().getProperty('fullname').decode('utf-8')
        coordinacion = Coordinaciones.getTerm( viaje.getOwner().getProperty('coordinacion')).title
    
        row = [colaborador,coordinacion,lugar,str(fecha_salida), str(fecha_regreso), str(avion), str(hotel), str(comidas), str(otros) , str(fecha_comprobacion_m), str(monto), str(fecha_finanzas_m)]

        return u",".join(row)


    def query_catalog(self, search_params):
        """
        search_params: diccionario que contiene los parámetros de búsqueda para el portal_catalog
        POR TERMINAR
        """
        print(search_params)
        comprobaciones = []
        try:
            pctl = self.context.portal_catalog
        except Exception as error:
            print(error)
            pctl = getToolByName(self.context, 'portal_catalog')
        brains = pctl(portal_type=['comprobacion'], Creator=search_params['user'].split("_"))
        #filter brains by date 
        for brain in brains:
            obj = brain.getObject()
            #Revisar fecha
            fecha_comprobacion = ""
            for w in obj.workflow_history['comprobacion_workflow']:
                if w['action'] == 'guardar':
                    if fecha_comprobacion == "":
                        fecha_comprobacion = w['time']
                    elif w['time'] > fecha_comprobacion:
                        fecha_comprobacion = w['time']
            mexico = pytz.timezone("America/Mexico_City")
            fecha_comprobacion_m = mexico.localize(fecha_comprobacion.utcdatetime())
            fecha_m = fecha_comprobacion_m.date()
            fechaI = datetime.strptime(search_params['date_ini'],"%Y-%m-%d").date()
            fechaF = datetime.strptime(search_params['date_fin'],"%Y-%m-%d").date()
            if fecha_m >= fechaI and fecha_m <= fechaF : #filter by date and owner area
                comprobaciones.append(obj)
        return comprobaciones

    def downloadFile(self):
        """
        Función para descarga de csv con encoding de windows
        """
        params = {'user': None, 'date_ini': None, 'date_fin': None, 'coordinacion': None}
        url_form = self.request.form
        if url_form:
            print(url_form)
            if url_form.has_key('user'): params['user'] = url_form['user']
            if url_form.has_key('date_ini'): params['date_ini'] = url_form['date_ini']
            if url_form.has_key('date_fin'): params['date_fin'] = url_form['date_fin']
            if url_form.has_key('coordinacion'): params['coordinacion'] = url_form['coordinacion']
            
        comps_list = self.query_catalog(params)
        
        header = u"Colaborador,Coordinación,Lugar,Fecha de salida, Fecha de regreso,Monto Avión,Monto Hotel,Monto Alimentos,Monto Otros,Fecha de Comprobación,Monto Aprobado,Fecha Autorización Finanzas,\n"
        
        body = u""
        for comprobacion in map(self.get_row, comps_list):
            body += comprobacion + u"\n"
            
        file_text = header.encode('cp1252') + body.encode('cp1252')
        blob = BlobFile(bytes(file_text), filename=('ReporteComprobaciones.csv').decode('utf-8'))

        """if blob is None:
	        raise NotFound('No file present')
        """
        filename = getattr(blob, 'filename', self.context.id + '_download')        
        set_headers(blob, self.request.response)

        self.request.response.setHeader('Content-Type', 'text/csv')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="%s"' % filename)

            #self.request.response.setBody('', lock=True)
            
        return stream_data(blob)

        
        
