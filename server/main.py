#!/usr/bin/env python3
################################# IMPORTS #####################################
import sys
import json
from warnings import warn
import pdb
import inspect
import traceback

from tornado.ioloop import IOLoop
from tornado.web import url  # constructs a URLSpec for you
# handlers
from tornado.web import RedirectHandler
from tornado.web import RequestHandler
from tornado.web import StaticFileHandler
from tornado.websocket import WebSocketHandler
# other
from tornado.web import Application
from tornado.web import Finish

from lib import config
from lib import clogging
log = clogging.getLogger('main', filename='main.log') # this must come BEFORE imports that use getLogger('main')
from lib.helper import random_string, reduce_string
from lib.node import create_appropriate_node
from lib.mongo import Mongo
from lib.user import User
from lib.math_graph import MathGraph
from lib import user
from lib.score import ScoreCard
from lib import auth
from lib.curriculum import Curriculum

# this and relevant code should eventually be migrated into auth module
import xml.etree.ElementTree as ET

################################# HELPERS #####################################
if sys.version_info[0] < 3 or sys.version_info[1] < 4:
	raise SystemExit('Please use Python version 3.4 or above')

def clean_and_verify_node_ids(dic):
	node_id_key_names = ['node_id', 'central_node_id', 'goal_id', 'pregoal_id']
	for key in node_id_key_names:
		if key in dic:
			the_id = dic[key]
			if the_id in our_MG.nodes():
				print('got unclean id: {}'.format(the_id))
				dic[key] = our_MG.n(the_id).id
				print('replaced with clean id: {}'.format(dic[key]))
			else:
				return False # to indicate failure
	return True


################################## MAIN #######################################


class BaseHandler(RequestHandler):


	def prepare(self):
		if self.request.host != 'provemath.org' and self.request.host != 'localhost':
			# note: the request.uri INCLUDES the query string
			self.redirect('http://provemath.org', self.request.uri)
			Finish()

	# this is for development only, and may not be needed when using incognito
	# mode anyway.  This must be commented out when moving to server.
	def set_extra_headers(self, path):
		# Disable cache
		self.set_header(
			'Cache-Control',
			'no-store, no-cache, must-revalidate, max-age=0')


class IndexHandler(BaseHandler):


	def get(self):
		user_dict = {}
		method = self.get_argument("method", default='', strip=False)
		authorization_code = self.get_argument("code", default='', strip=False)
		requested_id = self.get_argument("nodeid", default='', strip=True)

		if requested_id == '': # in this case, don't log in.  just show them what they want.  This path-like behavior will be removed once we change the oauth method.

			cookie = self.get_secure_cookie("mycookie")
			if cookie:
				print('COOKIE IS: '+str(cookie))
				user_identifier = json.loads(str(cookie, 'UTF-8'))
				print('user identifier IS: '+str(user_identifier))
				user = User(user_identifier)
				user_dict = user.dict # WHAT ABOUT THE PICTURE? maybe...
				# user_dict = provider.id_and_picture(request_root, user.dict)

			elif method is not '' and authorization_code is not '':
				redirect_response = 'https://{}/index?method={}&code={}&nodeid={}'.format(self.request.host, method, authorization_code, requested_id) # but this is still not enough for requested_id to work, since the oauth providers send you to a static url, they don't remember your query and send you back with the same query
				provider = auth.get_new_provider(method, host=self.request.host)
				try:
					provider.oauth_obj.fetch_token(
						provider.token_url,
						client_secret=provider.secret,
						authorization_response=redirect_response
						)
					user_info = provider.oauth_obj.get(provider.request_url)

					if provider.request_format == 'json':
						request_root = json.loads(user_info.text)
						account_id = request_root['id']
					else:
						request_root = ET.fromstring(user_info.text)
						account_id = request_root.find('id').text
					user = User({
						'type': provider.name,
						'id': account_id
					})
					user_dict = provider.id_and_picture(request_root, user.dict)
					print("logged in dict is:"+ str(user_dict)+"\n")
					self.set_secure_cookie("mycookie", json.dumps(user.identifier))
				except Exception as e:
					print('Login failed.  Exception message below:')
					print(e) # user_dict is still {}
					# inspect.stack()
					(typ, val, tb) = sys.exc_info()
					traceback.print_tb(tb)

			else:
				pass # user not logged in
		self.render("../www/index.html",
					user_dict_json_string=json.dumps(user_dict),
					host=self.request.host,
					subjects=json.dumps(list(config.public_starting_node_keys)),
					all_subjects=json.dumps(list(config.starting_nodes.keys())),
					javascript_kickoff_file=config.javascript_kickoff_file,
					LOCAL_ID_PREFIX=config.LOCAL_ID_PREFIX,
					requested_id=requested_id)


class PrintableContentHandler(BaseHandler):


	def get(self):
		requested_curriculum_id = self.get_argument('curriculumid', default=None, strip=True)
		requested_node_id = self.get_argument('nodeid', default=None, strip=True)
		if requested_curriculum_id is not None:
			curriculum = Curriculum(retrieve=True, wanted_id=requested_curriculum_id)
			content = curriculum.as_printable_html()
			self.render('../www/printable-content.html',
						content=content)
		elif requested_node_id is not None:
			node = our_MG.n(requested_node_id)
			content = node.as_printable_html()
			self.render('../www/printable-content.html',
						content=content)
		else:
			raise Exception('no node or curriculum specified')


class JSONHandler(BaseHandler):


	def get(self):
		# get appropriate subgraph from NewtorkX!
		json_graph = our_MG.as_complete_json() # TODO write this method
		self.write(json_graph)


# The WebSocket protocol is still in development. This module currently
# implements the "hixie-76" and "hybi-10" versions of the protocol. See
# this browser compatibility table on Wikipedia:
# http://en.wikipedia.org/wiki/WebSockets#Browser_support
class SocketHandler (WebSocketHandler):


	def __init__(self, application, request, **kwargs):
		WebSocketHandler.__init__(self, application, request, **kwargs)
		self.user = None

	def jsend(self, dic):
		if self.user:
			user_identifier = self.user.dict['account']
			dic['identifier'] = user_identifier
		else:
			dic['identifier'] = None
		self.write_message(dic)

	def open(self):
		# this happens BEFORE first-steps
		self.jsend({
			'command': 'populate-oauth-urls',
			'url_dict': auth.auth_url_dict(host=self.request.host),
		})

	def on_message(self, message):
		log.debug('got message: ' + message+"\n")
		ball = json.loads(message)
		# clean any node ids that ball might have (to allow for multiple names)
		success = clean_and_verify_node_ids(ball)
		if not success:
			self.jsend({
				'command': 'display-error',
				'message': 'The node you are trying to manipulate is not stored in the server, so no action will be taken on the server side.',
			})
			return

		# Respond to commands!
		if ball['command'] == 'print':
			print(ball['message'])

		elif ball['command'] == 'first-steps':
			# if a node was requested, send it immediately
			requested_id = ball['requested_id']
			if requested_id is not '':
				try:
					# self.request_nodes will fail if the requested_id does not exist
					self.request_nodes([requested_id], ball, userless=True)
					self.jsend({'command': 'open-node', 'node_id': requested_id})
				except ValueError:
					self.jsend({'command': 'display-error', 'message': 'Sorry, the requested node (with ID "{}") does not exist.'.format(requested_id)})

			# set up user and nodes
			self.user = User(ball['identifier'])
			self.jsend({'command': 'update-user'})
			if self.ids(ball):
				self.send_graph(ball)
			else: # they've learned nothing yet
				self.jsend({
					'command': 'prompt-starting-nodes',
				})

		elif ball['command'] == 'get-starting-nodes':
			subject = ball['subject']
			self.user.set_pref({'subject': subject})
			self.send_graph(ball)

		elif ball['command'] == 'get-curriculum':
			goal = ball['goal']

		elif ball['command'] == 'learn-node':
			command = self.user.learn_node(ball['node_id'])
			if command is not None:
				self.jsend(command)
			if ball['mode'] == 'learn':
				self.send_graph(ball)
			else:
				raise Exception('Mode is not learn.  Warning: That mode might not be implemented yet.')

		elif ball['command'] == 'unlearn-node':
			self.user.unlearn_node(ball['node_id'])

		elif ball['command'] == 'set-pref':
			self.user.set_pref(ball['pref_dict'])

		elif ball['command'] == 'save-node': # handles both new nodes and changes to nodes
			is_new = ball['is_new']
			node_dict = ball['node_dict']
			try:
				node_obj = create_appropriate_node(node_dict)
				log.debug('\nnode made.  looks like: {}'.format(node_obj))

				# take a look at the score card, to see if the node is worthy
				sc = node_obj.score_card()
				if not isinstance(sc, ScoreCard):
					raise TypeError('sc is not a ScoreCard.')
				if not sc.is_passing():
					raise Exception('Node not worthy to be saved.  Your score is {}.  Your strikes are: {}'.format(sc.total_score(), sc.as_dict()))

				log.debug('Now time to put node into the DB...\n')

				# take a look at the dependencies now
				# log.debug('node.id: {}'.format(node_obj.id))
				previous_node_dict = our_mongo.find_one({"_id": node_obj.id})
				if previous_node_dict is None: # it must be a brand new node!
					previous_dependency_ids = []
				else:
					# log.debug('prev_node_dict: {}'.format(previous_node_dict))
					previous_node = create_appropriate_node(previous_node_dict)
					# log.debug('prev_node: {}'.format(previous_node))
					previous_dependency_ids = previous_node.dependency_ids

				# log.debug('prev deps are: '+str(previous_dependency_ids))
				current_dependency_ids = node_obj.dependency_ids
				# log.debug('curr deps are: '+str(current_dependency_ids))
				new_dependency_ids = set(current_dependency_ids) - set(previous_dependency_ids)
				removed_dependency_ids = set(previous_dependency_ids) - set(current_dependency_ids)

				# VERIFY THAT THE GRAPH WITH THESE NEW ARCS IS STILL ACYCLIC:
				H = our_MG.copy()
				for new_dependency_id in new_dependency_ids:
					print('from {} to {}'.format(our_MG.n(new_dependency_id), node_obj))
					H.add_edge(new_dependency_id, node_obj.id)
					# print node_obj.attrs['name'].value + ' cannot depend on ' + our_MG.n(new_dependency_id).attrs['name'].value + ' because ' + our_MG.n(new_dependency_id).attrs['name'].value + ' already depends on ' + node_obj.attrs['name'].value + '!'
					H.validate()

				# add node to DB, changing the ID if necessary for a brand new node
				if is_new:
					old_JS_id = node_dict['_id']
					proposed_id = ball['proposed_id']
					good_id = our_mongo.proposed_id_to_good_id(proposed_id)
					node_obj._id = good_id
					our_mongo.insert_one(node_obj.as_dict())
					# tell client about new id
					self.jsend({
						'command': 'change-node-id',
						'old_node_id': old_JS_id,
						'new_node_id': node_obj.id,
					})
				else:
					our_mongo.replace_one({ "_id": node_obj.id }, node_obj.as_dict())

				update_our_MG()

				# send an update of the graph to the user if there are new dependencies:
				self.request_nodes(new_dependency_ids, ball)
				self.remove_client_edges(node_obj.id, removed_dependency_ids)
			except Exception as error:
				# stuff didn't work, send error back to user
				self.jsend({
					'command': 'display-error',
					'message': str(error),
				})
				log.warning('Error: '+str(error))
				(typ, val, tb) = sys.exc_info()
				traceback.print_tb(tb)

		elif ball['command'] == 're-center-graph':
			# We get the 5th nearest neighbors
			neighbors = our_MG.single_source_shortest_anydirectional_path_length(ball['central_node_id'], 1) # can just use digraph.anydirectional_neighbors
			H = our_MG.subgraph(list(neighbors.keys()))
			dict_graph = H.as_js_ready_dict()
			self.jsend({
				'command': 'load-graph',
				'new_graph': dict_graph,
			})

		elif ball['command'] == 'request-node':
			self.request_nodes([ball['node_id']], ball)

		elif ball['command'] == 'update-nodes':
			nodes_to_send = ball['client_node_ids']
			subgraph_to_send = our_MG.subgraph(nodes_to_send)
			dict_graph = subgraph_to_send.as_js_ready_dict()
			self.jsend({
				'command': 'load-graph',
				'new_graph': dict_graph,
			})

		elif ball['command'] == 'search':
			search_results = our_mongo.find({'$text':{'$search':ball['search_term']}},{'score':{'$meta':"textScore"}})
			self.jsend({
				'command': 'search-results',
				'results': list(search_results.sort([('score', {'$meta': 'textScore'})]).limit(18)),
			})

		elif ball['command'] == 'get-goal-suggestion':
			goal_id = our_MG.choose_goal(self.user)
			goal_node = our_MG.n(goal_id)
			self.jsend({
				'command': 'suggest-goal',
				'goal': goal_node.as_dict(),
			})

		elif ball['command'] == 'set-goal':
			goal_id = ball['goal_id']
			goal_node = our_MG.n(goal_id)
			self.user.set_pref({'goal_id': goal_id})
			self.send_graph(ball)
			self.jsend({
				'command': 'highlight-goal',
				'goal': goal_node.as_dict(),
			})

		elif ball['command'] == 'get-pregoal-suggestion':
			pregoal_id = our_MG.choose_learnable_pregoals(self.user, number=1)[0]
			pregoal_node = our_MG.n(pregoal_id)
			self.jsend({
				'command': 'suggest-pregoal',
				'pregoal': pregoal_node.as_dict(),
			})

		elif ball['command'] == 'set-pregoal':
			pregoal_id = ball['pregoal_id']
			pregoal_node = our_MG.n(pregoal_id)
			self.user.set_pref({'requested_pregoal_id': pregoal_id})
			self.send_graph(ball)
			self.jsend({
				'command': 'highlight-pregoal',
				'pregoal': pregoal_node.as_dict(),
			})

	def request_nodes(self, node_ids, ball, userless=False):
		# user manually requests a node.  So we want to preserve client_node_ids as not to change anything for them.  We only want to ADD the requested nodes additionally.
		for node_id in node_ids:
			if node_id not in our_MG.nodes():
				raise ValueError('The node_id "'+node_id+'" does not exist.')
		if userless:
			ids = set(node_ids)
		else:
			ids = set(self.ids(ball)).union(set(node_ids))
		H = our_MG.subgraph(ids)
		dict_graph = H.as_js_ready_dict()
		self.jsend({
			'command': 'load-graph',
			'new_graph': dict_graph,
		})

	def ids(self, ball):
		learned_ids = self.user.dict['learned_node_ids']
		return list(set(learned_ids).union(set(ball['client_node_ids'])))

	def remove_client_edges(self, node_id, dependency_ids):
		self.jsend({
			'command': 'remove-edges',
			'node_id': node_id,
			'dependency_ids': list(dependency_ids),
		})

	def send_graph(self, ball):
		subject = self.user.dict['prefs']['subject']
		log.debug('SUBJECT IS: ' + str(subject))
		log.debug('LOGGED IN AS: ' + str(self.user.identifier))
		nodes_to_send = our_MG.nodes_to_send(self.user, client_node_ids=ball['client_node_ids'])
		subgraph_to_send = our_MG.subgraph(nodes_to_send)
		dict_graph = subgraph_to_send.as_js_ready_dict()
		log.debug('js ready dict is {}'.format(dict_graph))
		self.jsend({
			'command': 'load-graph',
			'new_graph': dict_graph,
		})

	def starting_nodes(self, subject):
		return config.starting_nodes[subject]

	def on_close(self):
		print('A websocket has been closed.')


class StaticHandler(StaticFileHandler, BaseHandler):

	# A static file handler with our BaseHandler cachelessness and redirection.
	pass


class RedirectPreserveQueryHandler(BaseHandler):


	URL = None

	def initialize(self, url):
		self.URL = url

	def get(self):
		if self.URL is None:
			raise ValueError('No URL specified.')
		# see http://www.tornadoweb.org/en/stable/httputil.html#tornado.httputil.HTTPServerRequest
		uri_string = '{}?{}'.format(self.URL, self.request.query)
		self.redirect(uri_string)
		Finish()


def make_app():
	return Application(
		[
			url(r'(?:/(?:index(?:\.htm(?:l)?)?)?)?', IndexHandler, name="indexh"),
			url(r'/websocket', SocketHandler),
			url(r'/json', JSONHandler, name="jsonh"),
			url(r'/print', PrintableContentHandler, name="printh"),
			url(r'/docs(?:\.htm(?:l)?)?', RedirectHandler, {"url": "docs/index.html"}, name='docsh'),
			url(r'/docs/(.*)', StaticHandler, {"path": "../docs/build/html/"}),
			url(r'/image/(.*)', StaticHandler, {"path": "../server/data/graph-theory-images/"}), # ON THE OTHER HAND, images (plural) refers to the folder www/images
			url(r'/(.*)', StaticHandler, {"path": "../www/"}),
		],
		# settings:
		debug=True,
		cookie_secret=random_string(99)
	)

def make_app_and_start_listening():
	application = make_app()
	application.listen(80)
	IOLoop.current().start()

def update_our_MG():
	# 1. grab nodes and edges from database
	all_node_dicts = list(our_mongo.find())
	# print('number of node dicts is: {}'.format(len(all_node_dicts)))

	# 2. create a networkx graph with the info...
	global our_MG
	our_MG = MathGraph()
	for node_dict in all_node_dicts:
		# try:
		node = create_appropriate_node(node_dict)
		# except Exception as e:
			# print('\nerror.  could not create_appropriate_node.  node_dict was: '+str(strip_underscores(node_dict)))
		our_MG.add_n(node)
	for node_id in our_MG.nodes():
		node = our_MG.n(node_id)
		for dependency_id in node.dependency_ids:
			our_MG.add_edge(dependency_id, node_id)
	our_MG.validate() # make sure it's still Acyclic
	our_MG.remove_redundant_edges()
	print('Node array loaded with length: {}'.format(len(our_MG.nodes())))
	print('Edge array loaded with length: {}'.format(len(our_MG.edges())))

if __name__ == "__main__":
	print('\nSERVER RESTART.')

	# 0. create a global mongo object for later use (for upserts in the future)
	our_mongo = Mongo("provemath", "nodes")

	# 1 and 2
	update_our_MG()
	print('ids are: {}'.format(our_MG.nodes()))

	# 3. launch!
	make_app_and_start_listening()

