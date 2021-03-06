############################ IMPORTS #############################
# sys imports

# third party
import networkx as nx

# local
from lib.networkx.classes import dag
from lib.decorate import record_elapsed_time
from lib import helper
from lib.node import Node

############################ HELPERS #############################

############################## MAIN ##############################


class PMDAG (nx.DAG):
	""" Prove Math specific graph methods go here; that is, anything using our custom node objects.

	A few of the methods in here (unselected_dependency_tree, unselected_count, unselected_counts, and selectable_predestinations) could actually do just fine in nx.DAG, since they don't use our custom node objects ("self.n()").  However, I will leave them here because they seem to belong organizationally.

	REMEMBER that most of these functions take node IDs as inputs, even though the variables aren't called "target_id", for example!
	"""


	# FROM GRAPH:
	def n(self, node_id):
		assert isinstance(node_id, str) # or isinstance(node_id, bytes)
		return self.node[node_id]["custom_object"]

	def add_n(self, nodebunch):
		if not self.acceptable_iterable(nodebunch): # nodebunch must be a single node
			nodebunch = [nodebunch]
		for node in nodebunch:
			# verify that the node is legit
			assert isinstance(node, Node)
			# make sure the node doesn't already exist, as this would overwrite it
			assert not self.has_node(node.id)
			# add it
			self.add_node(node.id, attr_dict={"custom_object": node})

	def remove_n(self, nodebunch):
		if not self.acceptable_iterable(nodebunch): # nodebunch must be a single node
			nodebunch = [nodebunch]
		for node in nodebunch:
			self.remove_node(node.id)

	# FROM DIGRAPH:
	def as_js_ready_dict(self):
		d = dict()
		d['nodes'] = [self.n(node_id).as_dict() for node_id in self.nodes()]
		d['links'] = [{'source': source, 'target': target} for (source, target) in self.edges()]
		return d

	@record_elapsed_time
	def unselected_dependency_tree(self, target, selected_nodes):
		""" note that an unselected_dependency_tree is NOT necessarily a tree! """
		if not self.acceptable_iterable(selected_nodes):
			raise ValueError('Argument {} is not iterable'.format(selected_nodes))
		# graph.copy() is expensive operation, so instead we use nx.ancestors:
		# Remember, nx.ancestors does NOT include the target node itself
		ancestors = nx.ancestors(self, target).union({target})
		selected_ancestors = set()
		for selected_node in selected_nodes:
			to_add = nx.ancestors(self, selected_node).union({selected_node})
			selected_ancestors.update(to_add)
		return ancestors.difference(selected_ancestors)

	def unselected_count(self, target, selected_nodes):
		return len(self.unselected_dependency_tree(target, selected_nodes))

	def unselected_counts(self, target_bunch, selected_nodes):
		# this method is just a unselected dependency tree and unselected count combined
		if not self.acceptable_iterable(selected_nodes):
			raise ValueError('Argument {} is not iterable'.format(selected_nodes))
		G = self.copy()	# lets us bypass calling unselected_dependency_tree repeatedly
		G.remove_nodes_from(selected_nodes)
		return [len(G.ancestors(target).union({target})) for target in target_bunch]

	# FROM DAG
	@record_elapsed_time
	def importance_weight(self, node):
		distance_from_node = 0
		current_depth_nodes = {node}
		already_counted_nodes = set() # needed in case there are any cycles
		predecessors = {node}
		successors = {node}	#kept separate because descendants are given more weight than ancestors in asessing a node's importance
		ANCESTORS_DESCENDANTS_WEIGHT_FRACTION = 1/6
		NEIGHBOR_NORMALIZATION_FRACTION = 1/10 #rescales the sum of all neighbor importances to match the scale of the original node's own importance, i.e. [1,10]
		EXPECTED_NEIGHBORS_PER_NODE = 3

		norm_importances = [self.n(node).attrs['importance'].value] #normalized importance of the nodes in each depth level
		SEARCH_DEPTH_LIMIT = 4
		while distance_from_node < SEARCH_DEPTH_LIMIT:
			distance_from_node += 1
			if predecessors:
				predecessors = self.predecessors(predecessors) - already_counted_nodes	#needed in case there are any cycles
			else:
				predecessors = set()
			if successors:
				successors = self.successors(successors) - already_counted_nodes
			else:
				successors = set()
			if (len(successors) + len(predecessors)) == 0:	#no more neighbors, don't look any further
				norm_importances.append(0)
				break
			predecessors_importances = [ANCESTORS_DESCENDANTS_WEIGHT_FRACTION * self.n(n).attrs['importance'].value for n in predecessors]
			successors_importances = [(1-ANCESTORS_DESCENDANTS_WEIGHT_FRACTION) * self.n(n).attrs['importance'].value for n in successors]	#weighted toward descendants
			current_depth_importances = predecessors_importances + successors_importances

			current_depth_normalized_sum = sum(current_depth_importances) * NEIGHBOR_NORMALIZATION_FRACTION / (EXPECTED_NEIGHBORS_PER_NODE**distance_from_node)
			#As distance increases there are exponentially more neighbors.  The 1/(EXPECTED_NEIGHBORS_PER_NODE**distance) term counteracts this.
			norm_importances.append(current_depth_normalized_sum)

			already_counted_nodes = already_counted_nodes.union(predecessors)
			already_counted_nodes = already_counted_nodes.union(successors)
		weighted_importances = [(importance/(index+1)**2) for index, importance in enumerate(norm_importances)]	#normalized importance of the nodes in each depth level, weighted against distance from node
		neighbors_weight = sum(weighted_importances)
		return neighbors_weight #(neighbors_weight, self.n(node).id)

	@record_elapsed_time
	def most_important(self, nbunch, number=1):
		def most_important_sorter(node): # the "node" here is actually a node_id!
			# two sanity checks before returning
			assert isinstance(node, str)
			self.n(node)
			return (self.importance_weight(node), node)
		if number <= 0:
			raise ValueError('Must give number > 0')
		if len(nbunch) < number:
			raise ValueError('Asked for more nodes than you provided')
		nodes_by_importance = sorted(nbunch, key=most_important_sorter, reverse=True)
		num_to_return = min(len(nodes_by_importance), number) # in case there are not actually at least :number: nodes available in nbunch
		return nodes_by_importance[:num_to_return]

	@record_elapsed_time
	def choose_destination(self, axioms, selected_nodes): # short sighted, depth-first
		"""
		:returns: One immediate successor to selected_nodes which we should set as the new destination (chosen by depth, then learn count, then importance, then id).
		"""
		self.validate_input_nodes(axioms)
		self.validate_input_nodes(selected_nodes)

		depth_to_successors_dict = self.depth_to_successors_dict(axioms, selected_nodes)
		if not depth_to_successors_dict:
			unselected_axioms = set(axioms) - set(selected_nodes)
			if unselected_axioms:
				return list(unselected_axioms)[0]
			else:
				raise Exception('You\'ve selected EVERYTHING (in that subject)!!!!  :(')
		deepest_successors = list(depth_to_successors_dict.items())[0][1]
		if not deepest_successors:
			# no more successors.  the user has finished the subject and needs to choose a new one
			return None

		# Now sort the deepest successors by learn count, then by importance, and finally name to break a tie.
		# If we need better efficiency, use DiGraph.learn_counts(targets, selected_nodes)
		def unselected_count_sorter(successor):
			return (
				self.unselected_count(successor, selected_nodes),
				-self.importance_weight(successor),
				self.n(successor).id,
			)
		destination = sorted(deepest_successors, key=unselected_count_sorter)[0]
		return destination

	@record_elapsed_time
	def selectable_predestinations(self, destination, selected_nodes):
		# a predestination is an unselected dependency of the destination, or the destination itself
		unselected_dependency_graph = self.subgraph(self.unselected_dependency_tree(destination, selected_nodes))
		selectable_dependencies = unselected_dependency_graph.sources()
		return selectable_dependencies

	@record_elapsed_time
	def choose_selectable_predestinations(self, axioms, selected_nodes, number=1, destination=None):
		if destination is None:
			destination = self.choose_destination(axioms, selected_nodes)
		selectable_predestinations = self.selectable_predestinations(destination, selected_nodes)
		return self.most_important(selectable_predestinations, number)

	def linearized_predestinations(self, destination, selected_nodes=[], choice_function=None):
		""" Given some nodes to choose between, choice function decides which one the user should learn first. """
		sub = self.unselected_dependency_tree(destination, selected_nodes)
		predestination_graph = self.subgraph(sub)
		linearized_predestinations = []
		while predestination_graph.nodes():
			selectable_predestinations = predestination_graph.sources()
			if choice_function is None:
				next_predestination = predestination_graph.most_important(selectable_predestinations, 1)[0]
			else:
				next_predestination = choice_function(selectable_predestinations)
			predestination_graph.remove_node(next_predestination)
			linearized_predestinations.append(next_predestination)
		return linearized_predestinations

	def _linearized_predestinations2_eater(self, destination, selected_nodes=[], choice_function=None):
		""" helper function.  eats the graph as it processes, so make a copy! """
		deps = self.predecessors(destination) - set(selected_nodes)
		if len(deps) == 0:
			return [destination]
		if len(deps) >= 1:
			if choice_function is None:
				# self is NOT the ENTIRE provemath graph, so this could be undesireable
				dep = self.most_important(deps, 1)[0]
			else:
				dep = choice_function(deps)
			lin_piece1 = self._linearized_predestinations2_eater(dep, selected_nodes, choice_function)
			self.remove_nodes_from(lin_piece1)
			lin_piece2 = self._linearized_predestinations2_eater(destination, selected_nodes, choice_function)
			self.remove_nodes_from(lin_piece2) # unnecessary, but ok
			lin_nodes = lin_piece1 + lin_piece2
			return lin_nodes
		else:
			raise ValueError('len(deps) impossible value')

	def linearized_predestinations2(self, destination, selected_nodes=[], choice_function=None):
		""" Same as linearized_predestinations, but chooses recursively. """
		copy_graph = self.subgraph(self.unselected_dependency_tree(destination, selected_nodes))
		lin_nodes = copy_graph._linearized_predestinations2_eater(destination, selected_nodes, choice_function)
		return lin_nodes

