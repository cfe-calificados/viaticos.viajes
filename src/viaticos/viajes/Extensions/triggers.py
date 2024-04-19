# -*- coding: utf-8 -*- 
import os
from plone import api
from datetime import datetime
from z3c.relationfield import RelationValue, TemporaryRelationValue
from plone.uuid.interfaces import IUUID
from Products.CMFCore.utils import getToolByName
import socket
import ast
from zope.component import getUtility
from zope.intid.interfaces import IIntIds

""" Get name of SERVER """
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
URL="http://viaticos.cfecalificados.mx/"#"http://"+s.getsockname()[0]+":8080/"#
s.close()

def get_bosses(username, grupo):
    #import pdb; pdb.set_trace()
    membership = api.portal.get_tool('portal_membership')
    downward = membership.getMemberById(username).getProperty("downward")
    downward_dic = {}
    try:
        downward_dic = ast.literal_eval(downward)
    except SyntaxError:
        print("Missing hierarchy for "+username)
        
    for employee in grupo:
        tmp = {}
        downward = membership.getMemberById(employee).getProperty("downward")
        try:
            tmp = ast.literal_eval(downward)
        except SyntaxError:
            print("Missing hierarchy for "+employee)            
            downward_dic.update(tmp)
    return downward_dic


def users_mail(self, state_change, comp=None):
    membership = api.portal.get_tool('portal_membership')
    trip = state_change.object
    body = u"Estimado usuario,\n se le informa por este medio que su solicitud de gastos con título: '"+trip.title.encode('utf-8').decode('utf-8')+u"' fue aprobada por la administración o su autorizador, habiendo completado su registro. Intente visitar este enlace "+URL+state_change.object.virtual_url_path()+u" para consultar la información resultante del proceso."+(u" Pruebe visitar la comprobación de gastos iniciada gracias a este registro: "+comp.absolute_url() if comp else "")
    body2 = u"Estimado usuario,\n se le informa por este medio que la solicitud de gastos que supervisa con título: '"+trip.title.encode('utf-8').decode('utf-8')+u"' ha concluido su registro. Intente visitar este enlace "+URL+state_change.object.virtual_url_path()+u" para consultar la información resultante del proceso."+(u"Pruebe visitar la comprobación de gastos iniciada gracias a este registro: "+comp.absolute_url() if comp else "")
    obj_owner = membership.getMemberById(trip.owner_info()['id'])
    receivers = []
    bosses = []
    if trip.grupo:
        receivers = [x for x in trip.grupo]+([trip.owner_info()['id']] if trip.owner_info()['id'] not in trip.grupo else [])
    else:
        receivers.append(trip.owner_info()['id'])

    downward = obj_owner.getProperty("downward")
    downward_dic = {}
    try:
        downward_dic = ast.literal_eval(downward)
    except SyntaxError:
        print("Missing hierarchy for "+obj_owner.getUserName())
    grupo = state_change.object.grupo
    if grupo:        
        downward_dic = get_bosses(obj_owner.getUserName(), grupo)
    for boss in downward_dic:
        if boss == 'marcoa.gonzalez': continue
        jefe = membership.getMemberById(boss)
        bosses.append(jefe.getProperty("email"))

    grup = [membership.getMemberById(x).getProperty("email") for x in receivers]
    if 'marcoa.gonzalez@calificados.cfe.mx' in grup:
        grup.remove("marcoa.gonzalez@calificados.cfe.mx")
        grup += ["ana.franco@calificados.cfe.mx"]

    if 'marcoa.gonzalez@calificados.cfe.mx' in bosses:
        bosses.remove("marcoa.gonzalez@calificados.cfe.mx")
        #bosses += ["ana.franco@calificados.cfe.mx"] #PREGUNTAR A ADMON SI DEBO INLCUIRLA PARA LOS COORDINADORES
        
    api.portal.send_email(
        recipient=";".join(grup),   
        #recipient = "carlos.acosta@calificados.cfe.mx", #DEBUG
        sender="noreply@plone.org",
        subject="Solicitud de gastos registrada",
        body=body,
    )
    
    try:
        api.portal.send_email(
            recipient=";".join(bosses),
            #recipient = "carlos.acosta@calificados.cfe.mx", #DEBUG
            sender="noreply@plone.org",
            subject="Solicitud de gastos supervisada registrada",
            body=body2,
        )
    except:
        pass

def generate(viaje, n_grupo=1):
    if not viaje.anti_desc:
        return []
    desc_monto = [[elem.strip() for elem in x.split(":")] for x in viaje.anti_desc.split("\n")]
    grupo = []
    for x in desc_monto:
        print("adding new tuple")
        #import pdb; pdb.set_trace()
        grupo.append({'descripcion': u'Descripción', 'fecha': datetime.now(), 'concepto': x[0], 'importe': float(x[1])/n_grupo, 'archivo': None, 'comprobado':0.0, 'anticipo':u'anticipo', 'clave':8 if 'mida' in x[0] else 9, 'origen':'nacional', 'aprobado':0.0})
    return grupo#[{'descripcion': u'Descripción', 'fecha': datetime.now(), 'concepto': u'Concepto', 'importe': 0.0, 'archivo': None}]

def create_comprobaciones(portal, trip, rel_full):
    comprobaciones = []
    trip_owner = trip.getOwner().getUserName()
    full_grupo = list(trip.grupo)+([trip_owner] if trip_owner not in trip.grupo else [])
    #import pdb; pdb.set_trace()
    for employee in full_grupo:
        try:            
            comp_tmp = api.content.create(safe_id=True,type="comprobacion", relacion=rel_full, title=u"Comprobación de "+trip.title.encode('utf-8').decode('utf-8'), total_comprobar=(trip.anti_monto/len(full_grupo) if trip.anti_monto else 0.0), notas=u"", notas_finanzas=u"",notas_implant=u"", grupo_comprobacion=generate(trip, len(full_grupo)), container=portal.viaticos)            
            new_owner = api.user.get(username=employee).getUser()
            old_comp_owner = comp_tmp.getOwner() #1
            comp_tmp.changeOwnership(new_owner, recursive=False)
            comp_tmp.setCreators([employee])
            roles = list(comp_tmp.get_local_roles_for_userid(employee))
            if "Owner" not in roles: roles.append("Owner")
            if "Reviewer" not in roles: roles.append("Reviewer")
            if "Manager" in roles: roles.remove("Manager")
            comp_tmp.manage_setLocalRoles(employee, roles)
            comp_tmp.manage_setLocalRoles(old_comp_owner.getId(), ["Finanzas"]) #1
            comp_tmp.reindexObjectSecurity()
            pct = getToolByName(comp_tmp, 'portal_catalog')
            brain = pct({'portal_type': 'comprobacion', 'id': comp_tmp.id})[0]
            brain.changeOwnership(new_owner, recursive=True)
            brain.manage_setLocalRoles(employee, roles)
            brain.reindexObjectSecurity()
        except Exception as error:
            import pdb; pdb.set_trace()
            print("Creation of total elements failed...")
            return



def create_comprobacion(self, state_change):
    portal = api.portal.get()
    trip = state_change.object
    obj = None
    #trip_ctx = trip.aq_base
    #uuid = IUUID(trip_ctx)
    intids = getUtility(IIntIds)    
    #temp = TemporaryRelationValue(trip.absolute_url_path()) #Una relacion no formada completamente 
    rel_full = RelationValue(intids.getId(trip))#temp.convert()
    if trip.grupo:
        create_comprobaciones(portal, trip, rel_full)
        users_mail(self, state_change)
        return
    try:
        obj = api.content.create(safe_id=True,type="comprobacion", relacion=rel_full, title=u"Comprobación de "+trip.title.encode('utf-8').decode('utf-8'), total_comprobar=(trip.anti_monto if trip.anti_monto else 0.0), notas=u"", notas_finanzas=u"", notas_implant=u"", grupo_comprobacion=generate(trip), container=portal.viaticos)#api.content.create(safe_id=True,type="comprobacion", relacion=trip, title=u"Comprobación de "+trip.title.encode('utf-8').decode('utf-8'), fecha=datetime.now(), importe=0, descripcion=u"Descripción", archivo=None, container=portal.viaticos) #None#
    except Exception as error:
        print(error)
        import pdb; pdb.set_trace()
    if obj != None:
        print("We made it!")
        #import pdb; pdb.set_trace()
        try:
            #import pdb; pdb.set_trace()
            trip_owner = trip.getOwner()
            old_comp_owner = obj.getOwner() #1
            obj.changeOwnership(trip_owner, recursive=False)
            obj.setCreators([trip.getOwner().getId()])
            roles = list(obj.get_local_roles_for_userid(trip.getOwner().getId()))
            if "Owner" not in roles: roles.append("Owner")
            if "Reviewer" not in roles: roles.append("Reviewer")
            if "Manager" in roles: roles.remove("Manager")
            obj.manage_setLocalRoles(trip.getOwner().getId(), roles)
            obj.manage_setLocalRoles(old_comp_owner.getId(), ["Finanzas"]) #1
            obj.reindexObjectSecurity()
            pct = getToolByName(obj, 'portal_catalog')
            brain = pct({'portal_type': 'comprobacion', 'id': obj.id})[0]
            brain.changeOwnership(trip_owner, recursive=True)
            brain.manage_setLocalRoles(trip.getOwner().getId(), roles)
            brain.reindexObjectSecurity()
            #print(obj.listCreators(), obj.listCreators__roles__)
        except Exception as error:
            print("Algo fallo: revisar.")
            import pdb; pdb.set_trace()

    else:        
        print("Algo malo pasó")

    users_mail(self, state_change, obj)
