# -*- coding: utf-8 -*-
from plone.dexterity.browser.view import DefaultView
from plone import api
from ..Extensions.triggers import generate

from plone.namedfile.utils import set_headers
from plone.namedfile.utils import stream_data
from Products.Five import BrowserView
from zope.publisher.interfaces import NotFound
from plone.namedfile.file import NamedBlobFile
import ast
from plone.app.textfield.interfaces import ITransformer

## PDF creation
from datetime import datetime
import locale
from su_pre_fixes import *
import os, subprocess
from hierarchy import Coordinaciones


def complete_m(motivo):
    trade = {"convenio_modificatorio": "un convenio modificatorio", "contacto":u"el contacto inicial con un cliente", "info":u"una adquisición de información", "propuesta":u"una propuesta comercial", "negociacion":u"una negociación", "contrato":u"una firma de contrato", "proceso":u"un proceso de entrega de servicio", "visita_tec":u"una visita técnica", "servicio_cliente":u"una visita de servicio al cliente", "evento":u"una asistencia a un congreso, foro o evento especializado", "capacitacion":u"una capacitación", "otro":u"un requerimiento de su área"}
    return trade[motivo]

def extract_info(obj_comp):
    locale.setlocale(locale.LC_TIME, 'es_MX.utf-8')
    viaje = None
    catalog = api.portal.get_tool('portal_catalog')
    if not obj_comp.relacion.isBroken():            
        brains = catalog(path={'query': obj_comp.relacion.to_path, 'depth': 0})
        viaje = brains[0].getObject()
    owner_member = obj_comp.getOwner()
    collected = {}
    collected['employee'] = owner_member.getProperty("fullname").decode('utf-8')
    collected['n_employee'] = owner_member.getProperty("numero_empleado")#u"311154"#
    #import pdb; pdb.set_trace()
    collected['trip_title'] = viaje.Title().decode('utf-8')+" en "+viaje.ciudad+", "+(viaje.pais if viaje.pais != u'Mexico' else u'México')
    collected['area'] = Coordinaciones.getTerm(owner_member.getProperty("coordinacion")).title
    collected['date_comp'] = datetime.now().strftime("%A %d de %B de %Y").decode('utf-8')
    collected['grupo_comp_ord'] = [x for x in sorted(obj_comp.grupo_comprobacion, key=lambda(x): x['fecha']) if x['anticipo'] != 'devolucion' ]
    collected['fecha_mod'] = obj_comp.modified().strftime("%d/%m/%Y")
    collected['date_ini'] = viaje.fecha_salida.strftime("%d/%m/%Y")#collected['grupo_comp_ord'][0]['fecha'].strftime("%d/%m/%Y").decode('utf-8')
    collected['date_fin'] = viaje.fecha_regreso.strftime("%d/%m/%Y")#collected['grupo_comp_ord'][-1]['fecha'].strftime("%d/%m/%Y").decode('utf-8')
    collected['notas'] = obj_comp.notas.encode('utf-8').decode('utf-8') if obj_comp.notas else ""
    collected['notas_finanzas'] = obj_comp.notas_finanzas.encode('utf-8').decode('utf-8') if obj_comp.notas_finanzas else ""
    collected['notas_implant'] = obj_comp.notas_implant.encode('utf-8').decode('utf-8') if obj_comp.notas_implant else ""
    collected['motivo'] = complete_m(viaje.motivo)
    transformer = ITransformer(viaje)    
    collected['objetivo'] = transformer(viaje.objetivo, 'text/plain') if viaje.objetivo else ""

    ## Limpiando de caracteres que rompen latex 
    collected['objetivo'] = collected['objetivo'].replace(u"""\r\n""", u"""\\\\""").replace(u'\xa0', u' ').replace("$", "\$").replace("&", "\&").replace("_", "\_")
    collected['notas'] = collected['notas'].replace(u"$", u"\$")
    #collected['notas'] = collected['notas'].replace(u"=", u"\=")
    collected['notas'] = collected['notas'].replace(u"\n", u" \\ ")

    collected['notas_finanzas'] = collected['notas_finanzas'].replace(u"$", u"\$")
    collected['notas_finanzas'] = collected['notas_finanzas'].replace(u"\n", u" \\ ")
    collected['notas_implant'] = collected['notas_implant'].replace(u"$", u"\$")
    collected['notas_implant'] = collected['notas_implant'].replace(u"\n", u" \\ ")

    collected['trip_title'] = collected['trip_title'].replace(u"°", u"$^\circ$")

    ### Nuevo desmadre para obtener al autorizador
    #import pdb; pdb.set_trace()
    upward_dic = {}    
    try:
        membership = obj_comp.portal_membership
        upward = owner_member.getProperty("downward")
        upward_dic = ast.literal_eval(upward)
    except Exception:
        print("Missing hierarchy")
    ### Termina desmadre
    
    boss = "FIRMA DEL COORDINADOR"
    if upward_dic:
        boss_member = membership.getMemberById(upward_dic.keys()[0])
        if boss_member:
            boss = boss_member.getProperty("fullname").decode('utf-8')
    collected['boss'] = boss   
    return collected
    
    
def gen_latex(obj_comp):
    full_data = extract_info(obj_comp)
    inner = u"""
    \\begin{document}
    \\begin{multicols}{2}
    \\flushleft{\\textbf{Nombre del empleado:} """+full_data['employee']+"}"
    inner += u"""
    \\vfill\\null
    \\columnbreak
    \\flushright{\\textbf{Empleado No.} """+full_data['n_employee']+"}"
    inner += u"""
    \\end{multicols}

    \\begin{multicols}{2}
    \\flushleft{\\textbf{Gastos efectuados en:} """+full_data['trip_title']+"}"
    inner += u"""
    \\vfill\\null
    \\columnbreak
    \\flushright{Periodo del """+full_data['date_ini']+" al "+full_data['date_fin']+u"\\\\ Fecha de comprobación: "+full_data['fecha_mod']+"}"
    inner += u"""
    \\end{multicols}

    \\begin{center}
    \\textbf{Área:} """+full_data['area']+u" \\hspace{1cm} \\textbf{Año:} "+str(datetime.now().year)
    inner += u"""
    \\end{center}

    \\bigskip
    
    """

    if full_data['notas']:
        inner += u"""
        \\noindent\\fbox{
        \\parbox{\\textwidth}{\\textbf{Notas del solicitante:} """+full_data['notas']+"}}"+"""
        \\\\~\\\\"""

    if full_data['notas_finanzas']:
        inner += u"""        
        \\noindent\\fbox{
        \\parbox{\\textwidth}{\\textbf{Notas de Finanzas:} """+full_data['notas_finanzas']+"}}"+"""
        \\\\~\\\\"""

    if full_data['notas_implant']:
        inner += u"""
        \\noindent\\fbox{
        \\parbox{\\textwidth}{\\textbf{Notas de Implant:} """+full_data['notas_implant']+"}}"


    if full_data['motivo']:
        inner += u"""
        \\textbf{Motivo:} """+full_data['motivo']+u"""\\\\
        
        """


    if full_data['objetivo']:
        inner += u"""
        \\textbf{Objetivo:} """+full_data['objetivo']+u"""\\\\
        
        """
        
    
    if full_data['grupo_comp_ord']:
        inner += u"""
        {\\fontfamily{lmss}\\selectfont
        \\begin{center}
        {\\rowcolors{7}{califigris}{califigrisecito}
        \\begin{tabularx}{\\textwidth}{|| >{\\centering\\arraybackslash}X | >{\\centering\\arraybackslash}X | >{\\centering\\arraybackslash}X | >{\\centering\\arraybackslash}X | >{\\centering\\arraybackslash}X | >{\\centering\\arraybackslash}X | >{\\centering\\arraybackslash}X ||}
        \\hline
        \\rowcolor{califiverde}
        \\begin{center} \\textbf{Fecha} \\end{center} & \\begin{center} \\textbf{Clave del gasto} \\end{center} & \\begin{center} \\textbf{Aprobado} \\end{center} & \\begin{center} \\textbf{I.V.A} \\end{center} & \\begin{center} \\textbf{Total} \\end{center} & \\begin{center} \\textbf{Descripción} \\end{center} \\\\
        \\hline \\hline"""
        totales = [0.0,0.0,0.0]
        for concepto in full_data['grupo_comp_ord']:
            iva = round(concepto['aprobado']*0.16, 2) if concepto['origen'] == 'nacional' else 0.0
            total_concepto = concepto['aprobado']
            inner += concepto['fecha'].strftime("%d/%m/%Y") +" & "+ str(concepto['clave']) +" & \\$" + str(round(concepto['aprobado']-(concepto['aprobado']*0.16), 2) if concepto['origen'] == 'nacional' else concepto['aprobado']) +" & "+ "\\$"+str(iva) + " & "+"\\$"+str(total_concepto)+" & "+concepto['concepto']
            totales = [totales[x]+y for x,y in enumerate([round(concepto['aprobado']-(concepto['aprobado']*0.16), 2), iva, total_concepto])]
            inner += "\\\\ \n\\hline"

        inner += u"""
        \\hline
         \\multicolumn{1}{c}{} & \\multicolumn{1}{c|}{\\textbf{Total}} & """
        inner += "\\$"+str(totales[0])+" & \\$"+str(totales[1])+ " & \\multicolumn{1}{c}{\\$"+str(totales[2])+u"""} & \\multicolumn{1}{c||}{}\\\\"""
        inner += u"""
        \\end{tabularx}
        }
        \\end{center}
        }
        
        \\bigskip"""
        #import pdb; pdb.set_trace()
        return headers+inner+(footer.replace("FIRMA DEL EMPLEADO", full_data['employee']).replace("FIRMA DEL COORDINADOR", full_data['boss']))



class ResetComprobacion(DefaultView):
    """ Vista por defecto para reinicialización de comprobación de gastos """

    def __call__(self):
        #import pdb; pdb.set_trace()
        if not self.request.form:
            authenticator = self.context.restrictedTraverse("@@authenticator")
            self.request.form['_authenticator'] = authenticator.token()
        if self.request.form:
            self.reset_comprobacion()
        self.request.response.redirect(self.context.absolute_url())

    def reset_comprobacion(self):
        #import pdb; pdb.set_trace()
        #print(u"reinicializando: "+self.context.title)
        catalog = api.portal.get_tool('portal_catalog')
        viaje = None
        if not self.context.relacion.isBroken():            
            brains = catalog(path={'query': self.context.relacion.to_path, 'depth': 0})
            viaje = brains[0].getObject()
        trip_owner = viaje.getOwner().getUserName()
        full_grupo = list(viaje.grupo)+([trip_owner] if trip_owner not in viaje.grupo else [])
        nuevas = generate(viaje, len(full_grupo))
        self.context.grupo_comprobacion = nuevas
        print("done", nuevas)
        
        

class DescargaComprobacion(BrowserView):
    """ Stream file and image downloads.
    """

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self):
        """Stream BLOB of context ``file`` field to the browser.

        @param file: Blob object
        """
        #import pdb; pdb.set_trace()
        if not os.path.exists("latex"):
            os.makedirs("latex")
        name = self.context.id+"_"+str(datetime.now()).replace(" ", "_")
        latex_code = gen_latex(self.context)
        with open("latex/"+name+".tex", "w") as latex:
            latex.write(latex_code.encode('utf-8'))
        try:
            proc = subprocess.call(["pdflatex", "-interaction=nonstopmode", "-output-directory=latex", "latex/"+name+".tex"])
            if proc:
                print("TeX compilation unsuccessfull")
                #import pdb; pdb.set_trace()
                return "Error"
        except Exception as error:
            print(error)
            #import pdb; pdb.set_trace()
            return "Error"
        
        proof = open("latex/"+name+".pdf", "rb")
        flow = proof.read()
        proof.close()
        blob = NamedBlobFile(flow, filename=(name+'.pdf').decode('utf-8'))
        if blob is None:
            raise NotFound('No file present')
        # Try determine blob name and default to "context_id_download."
        # This is only visible if the user tried to save the file to local
        # computer.
        filename = getattr(blob, 'filename', self.context.id + '_download')

        set_headers(blob, self.request.response)

        # Set Content-Disposition
        '''
        self.request.response.setHeader(
            'Content-Disposition',
            'inline; filename={0}'.format(filename)
        )
        '''
        self.request.response.setHeader('Content-Type', 'application/pdf')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="%s"' % filename)

        # Sets Content-Type and Content-Length
        #import pdb; pdb.set_trace()
        return stream_data(blob)
        #return blob
        #return flow


class Redireccion(BrowserView):
    def __call__(self):
        print("redirigiendoooo")
        return self.request.response.redirect("http://rh.cfecalificados.mx")
