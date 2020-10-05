# -*- coding: utf-8 -*-
from openerp import http

# class Pg2NotasCredito(http.Controller):
#     @http.route('/pg2__notas_credito/pg2__notas_credito/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/pg2__notas_credito/pg2__notas_credito/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('pg2__notas_credito.listing', {
#             'root': '/pg2__notas_credito/pg2__notas_credito',
#             'objects': http.request.env['pg2__notas_credito.pg2__notas_credito'].search([]),
#         })

#     @http.route('/pg2__notas_credito/pg2__notas_credito/objects/<model("pg2__notas_credito.pg2__notas_credito"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('pg2__notas_credito.object', {
#             'object': obj
#         })