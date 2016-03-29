################################## IMPORTS ####################################
import networkx as nx
import pytest

from lib.networkx.classes import digraph_extend
#for test_most_important:
#from lib.networkx.classes import dag
from lib.node import create_appropriate_node, Node

#################################### MAIN #####################################
def test_is_nonnull(): # this is here really to make sure DiGraph inherited is_nonnull from Graph
	nn = nx.DiGraph()
	nn.add_node('a')
	assert nn.is_nonnull()

	nonnull = nx.DiGraph()
	nonnull.add_edge('s', 't')
	assert nonnull.is_nonnull()

	null = nx.DiGraph()
	assert null.is_nonnull() == False

def test_validate():
	DG = nx.DiGraph()
	DG.add_edges_from([
		['a', 'b'],
		['c', 'd'],
	])
	assert DG.validate()

	try:
		DG.to_undirected().validate()
		assert False
	except AttributeError as e:
		assert str(e) == "'Graph' object has no attribute 'validate'"

def test_predecessor():
	DG = nx.DiGraph()
	DG.add_edges_from([
		['y', 'c'],
		['t', 'c'], ['c', 'd'],
	])
	assert DG.predecessor('c') in {'y', 't'}

def test_successor():
	DG = nx.DiGraph()
	DG.add_edges_from([
		['y', 'c'], ['c', 'L'],
		['t', 'c'], ['c', 'd'],
	])
	assert DG.successor('c') in {'d', 'L'}

def test_is_source():
	DG = nx.DiGraph()
	DG.add_edges_from([
		['y', 'c'], ['c', 'L'],
		['t', 'c'], ['c', 'd'],
	])
	assert DG.is_source('y')
	assert DG.is_source('t')
	assert DG.is_source('c') == False
	assert DG.is_source('d') == False

def test_shortest_path(): # this tests the BUILT-IN function for DiGraphs, which finds the shortest DIRECTED path
	DG = nx.DiGraph()
	DG.add_edges_from([
		['a', '1'], ['1', 'u'], ['u', '2'], ['2', 'd'],
		['b', 'm'],
		['c', 'm'],
	])
	assert DG.shortest_path('a', 'd') == ['a', '1', 'u', '2', 'd']
	assert DG.shortest_path('d', 'a') == None
	assert DG.shortest_path('c', 'b') == None
	assert DG.shortest_path({'a', 'b'}, {'c', 'd'}) == ['a', '1', 'u', '2', 'd']

def test_shortest_anydirectional_path():
	DG = nx.DiGraph()
	DG.add_edges_from([
		['y', 'c'], ['c', 'L'],
		['t', 'c'], ['c', 'd'],
	])
	assert DG.shortest_anydirectional_path('y', 'L') == ['y', 'c', 'L']
	assert DG.shortest_anydirectional_path('d', 't') == ['d', 'c', 't']
	assert DG.shortest_anydirectional_path('d', 'L') == ['d', 'c', 'L']
	assert DG.shortest_anydirectional_path('y', 't') == ['y', 'c', 't']

	# assert DG.shortest_anydirectional_path(['y', 'c'], ['L', 'd']) == (['c', 'L'] or ['c', 'd'])
	assert DG.shortest_anydirectional_path({'c', 'y'}, 'd') == ['c', 'd']

	DG.add_node('z')
	assert DG.shortest_anydirectional_path('z', 'c') == None

def test_ancestors():
	DG = nx.DiGraph()
	DG.add_path(['x', 'y', 'z'])
	
	#testing nonexistent inputs:
	with pytest.raises(nx.NetworkXError):
		DG.ancestors('NotANode')
	with pytest.raises(nx.NetworkXError):
		DG.ancestors(['NotANode'])
	with pytest.raises(nx.NetworkXError):
		DG.ancestors(['x', 'NotANode', 'z'])
	with pytest.raises(ValueError):
		DG.ancestors([])
	
	#existing inputs:
	assert DG.ancestors('z') == {'x', 'y'}
	assert DG.ancestors('y') == {'x'}
	assert DG.ancestors('x') == set()
	assert DG.ancestors(['x']) == set()

	DG = nx.DiGraph()
	DG.add_path(['x', 'y', 'z'])
	DG.add_edges_from([
		['a', 'x'], ['b', 'y'], ['c', 'z']
	])
	assert DG.ancestors('z') == {'y', 'x', 'c', 'b', 'a'}
	assert DG.ancestors('y') == {'x', 'b', 'a'}
	assert DG.ancestors(['y', 'x']) == {'b', 'a'}
	
	DG = nx.DiGraph()
	DG.add_path(['x', 'y', 'z'])
	DG.add_path(['a', 'b', 'c'])	#disconnected paths
	assert DG.ancestors(['c', 'z']) == {'b', 'a', 'y', 'x'}
	assert DG.ancestors(['a', 'x']) == set()
	assert DG.ancestors(['a', 'y']) == {'x'}
	DG.add_path(['x', 'b'])
	assert DG.ancestors(['c', 'z']) == {'b', 'a', 'y', 'x'}	

def test_common_ancestors():
	DG = nx.DiGraph()
	DG.add_path(['a', 'x'])
	DG.add_path(['b', 'y'])

	#testing nonexistent inputs:
	with pytest.raises(nx.NetworkXError):
		DG.common_ancestors(['NotANode'], 'y')
	with pytest.raises(nx.NetworkXError):
		DG.common_ancestors('NotANode','StillNotANode')
	with pytest.raises(ValueError):
		DG.common_ancestors([],'y')
	#existing inputs:
	assert DG.common_ancestors('x', 'y') == set()
	assert DG.common_ancestors(['x', 'y'], 'x') == {'a'}

	DG = nx.DiGraph()
	DG.add_nodes_from(['x', 'y'])
	assert DG.common_ancestors('x', 'y') == set()
	
	DG = nx.DiGraph()	
	DG.add_edges_from([['a', 'x'], ['c', 'y']])
	assert DG.common_ancestors('x', 'y') == set()

	DG = nx.DiGraph()
	DG.add_edges_from([
		['a', 'x'], ['b', 'x'], ['b', 'y'], ['c', 'y']
	])
	assert DG.common_ancestors('x', 'y') == {'b'}
	
	DG = nx.DiGraph()
	DG.add_edges_from([
		['a', 'x'], ['b', 'x'], 
		['b', 'y'], ['c', 'y'], 
		['d', 'b']
	])
	assert DG.common_ancestors('x', 'y') == {'b','d'}
	
	DG = nx.DiGraph()
	DG.add_edges_from([
		['a', 'x'], ['b', 'y'],
		['b', 'z'], ['c', 'z']
	])
	assert DG.common_ancestors(['x', 'y'], 'z') == {'b'}
	DG.add_edge('a', 'z')
	assert DG.common_ancestors(['x', 'y'], 'z') == {'a', 'b'}
	
def test_descendants():
	DG = nx.DiGraph()
	DG.add_path(['x', 'y', 'z'])

	#testing nonexistent inputs:
	with pytest.raises(nx.NetworkXError):
		DG.descendants('NotANode')
	with pytest.raises(nx.NetworkXError):
		DG.descendants(['NotANode'])
	with pytest.raises(nx.NetworkXError):
		DG.descendants(['x', 'NotANode', 'z']);

	#existing inputs:
	assert DG.descendants('x') == {'y', 'z'}
	assert DG.descendants('y') == {'z'}
	assert DG.descendants('z') == set()
	
	DG = nx.DiGraph()
	DG.add_path(['x', 'y', 'z'])
	DG.add_edges_from([
			['x', 'a'], ['y', 'b'], ['z', 'c']
	])
	assert DG.descendants('x') == {'y', 'z', 'a', 'b', 'c'}
	assert DG.descendants('y') == {'z', 'b', 'c'}
	
	DG = nx.DiGraph()
	DG.add_path(['x', 'y', 'z'])
	DG.add_path(['a', 'b', 'c'])
	assert DG.descendants(['a', 'z']) == {'b', 'c'}
	assert DG.descendants(['c', 'z']) == set()
	DG.add_path(['x', 'b'])
	assert DG.descendants(['a', 'z']) == {'b', 'c'}

def test_common_descendants():
	DG = nx.DiGraph()
	DG.add_path(['x', 'a'])
	DG.add_path(['y', 'b'])

	#testing nonexistent inputs:
	with pytest.raises(nx.NetworkXError):
		DG.common_descendants(['NotANode'], 'y')
	with pytest.raises(nx.NetworkXError):
		DG.common_descendants('NotANode','StillNotANode')
	with pytest.raises(ValueError):
		DG.common_descendants([],'y')
	#existing inputs:
	assert DG.common_descendants('x', 'y') == set()
	assert DG.common_descendants(['x', 'y'], 'x') == {'a'}

	DG = nx.DiGraph()
	DG.add_nodes_from(['x', 'y'])
	assert DG.common_descendants('x', 'y') == set()
	
	DG = nx.DiGraph()	
	DG.add_edges_from([['x', 'a'], ['y', 'c']])
	assert DG.common_descendants('x', 'y') == set()

	DG = nx.DiGraph()
	DG.add_edges_from([
		['x', 'a'], ['x', 'b'], ['y', 'b'], ['y', 'c']
	])
	assert DG.common_descendants('x', 'y') == {'b'}
	
	DG = nx.DiGraph()
	DG.add_edges_from([
		['x', 'a'], ['x', 'b'], 
		['y', 'b'], ['y', 'c'], 
		['b', 'd']
	])
	assert DG.common_descendants('x', 'y') == {'b','d'}
	
	DG = nx.DiGraph()
	DG.add_edges_from([
		['x', 'a'], ['y', 'b'],
		['z', 'b'], ['z', 'c']
	])
	assert DG.common_descendants(['x', 'y'], 'z') == {'b'}
	DG.add_edge('z', 'a')
	assert DG.common_descendants(['x', 'y'], 'z') == {'a', 'b'}
	
	
def test_hanging_dominion():
	DG = nx.DiGraph()
	DG.add_edges_from([
		['y', 'c'], ['c', 'L'],
		['t', 'c'], ['c', 'd'],
	])
	assert DG.hanging_dominion(['y']) == set('c')
	assert DG.hanging_dominion(['y', 't']) == set('c')
	assert DG.hanging_dominion(['c']) == {'L', 'd'}
	assert DG.hanging_dominion(['y', 'c']) == {'L', 'd'}

def test_absolute_dominion():
	DG = nx.DiGraph()
	DG.add_edges_from([
		['y', 'c'], ['c', 'L'],
		['t', 'c'], ['c', 'd'],
	])
	assert DG.absolute_dominion(['y']) == ['y']
	assert set(DG.absolute_dominion(['y', 't'])) == {'c', 'y', 't'}
	assert set(DG.absolute_dominion(['y', 'c'])) == {'L', 'd', 'y', 'c'}

	DG = nx.DiGraph()
	DG.add_edges_from([
		['a', 'b'], ['b', 'c'],
		['x', 'c'],
	])
	assert set(DG.absolute_dominion(['a', 'x'])) == {'b', 'a', 'x'}

def test_single_source_shortest_anydirectional_path_length():
	G = nx.DiGraph()
	G.add_path([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
	x = G.single_source_shortest_anydirectional_path_length(5, 3)
	assert len(x) == 7
	assert x == {
		2: 3,
		3: 2,
		4: 1,
		5: 0,
		6: 1,
		7: 2,
		8: 3,
	}

def test_multiple_sources_shortest_path_length():
	G = nx.DiGraph()
	G.add_path([0, 1, 2, 3, 4, 5, 6])
	d = G.multiple_sources_shortest_path_length([3], 2)
	assert d == {3:0, 4:1, 5:2}

	G = nx.DiGraph()
	G.add_path([0, 1, 2, 3, 4, 5, 6])
	d = G.multiple_sources_shortest_path_length([3, 4], 2)
	assert d == {3:0, 4:0, 5:1, 6:2}

	G = nx.DiGraph()
	G.add_path(['a', 'y', 'd'])
	G.add_path(['a', 'l', 'x'])
	G.add_path(['a', 'c'])
	G.add_path(['b', 'c'])
	G.add_path(['b', 'd', 'l'])
	G.add_path(['b', 't', 'x'])
	d = G.multiple_sources_shortest_path_length(['a', 'b'])
	assert d == {
		'a': 0, 'b': 0,
		'c': 1, 'y': 1, 'd': 1, 'l': 1, 't': 1,
		'x': 2,
	}



def test_unlearned_dependency_tree():
	DG = nx.DiGraph()
	DG.add_path(['l1', 't'])
	assert DG.unlearned_dependency_tree('t', ['l1']) == set()
	
	DG = nx.DiGraph()
	DG.add_path(['l1', 'u1', 't']) #learned, unlearned, target
	with pytest.raises(nx.NetworkXError):
		DG.unlearned_dependency_tree('NotANode', ['l1'])
	with pytest.raises(nx.NetworkXError):
		DG.unlearned_dependency_tree(['t'], ['l1'])
#	with pytest.raises(nx.NetworkXError):
#		print('\n',DG.unlearned_dependency_tree('t', ['NotANode']),'\n')
	assert DG.unlearned_dependency_tree('t', ['l1']) == {'u1'}
	assert DG.unlearned_dependency_tree('t', []) == {'l1', 'u1'}

	DG = nx.DiGraph()
	DG.add_path(['l1', 'u1', 't'])
	DG.add_path(['u2', 'u1'])
	assert DG.unlearned_dependency_tree('t', ['l1']) == {'u1', 'u2'}
	assert DG.unlearned_dependency_tree('t', []) == {'u1', 'u2', 'l1'}
	assert DG.unlearned_dependency_tree('t', ['l1', 'u1']) == set()
	
	DG = nx.DiGraph()
	DG.add_path(['l1', 'u1', 't'])
	DG.add_edge('u2', 't')
	assert DG.unlearned_dependency_tree('t', ['l1']) == {'u1', 'u2'}
	
	DG = nx.DiGraph()
	DG.add_path(['l1', 'u1', 't'])
	DG.add_edge('u3', 'l1')
	assert DG.unlearned_dependency_tree('t', ['l1']) == {'u1'}
	
	DG = nx.DiGraph()
	DG.add_path(['l1', 'u1', 't'])
	DG.add_path(['u4', 'l2', 't'])
	assert DG.unlearned_dependency_tree('t', ['l1', 'l2']) == {'u1'}

#def test_get_all_successors:
	#

#def test_get_all_predecessors:
	#

#def test_most_important_weight:
	#

def test_most_important():
	print("\n")
#prenodes need "type","def","description","name","importance"
	pre_a = {"type":"theorem","description":"This is node aaaaaaaaaa","name":"A","importance":2}
	# a = create_appropriate_node(pre_a)
	a = Node(pre_a)
	pre_b = {"type":"theorem","description":"This is node bbbbbbbbbb","name":"B","importance":4}
	b = create_appropriate_node(pre_b)
	pre_c = {"type":"theorem","description":"This is node cccccccccc","name":"C","importance":4}
	c = create_appropriate_node(pre_c)
	pre_d = {"type":"theorem","description":"This is node dddddddddd","name":"D","importance":6}
	d = create_appropriate_node(pre_d)
	
	#testing sort by node's own importance and id
	DG = nx.DiGraph()
	with pytest.raises(ValueError):
		DG.most_important(1, [])
	DG.add_n(a)
	node_list = DG.nodes()
	assert DG.most_important(1, node_list) == ['a']
	with pytest.raises(ValueError):
		DG.most_important(-1, node_list)
	DG.add_n(b)
	node_list = DG.nodes()
	assert DG.most_important(1, node_list) == ['b']
	assert DG.most_important(2, node_list) == ['b', 'a']
	with pytest.raises(ValueError):
		DG.most_important(4, node_list) == ['b', 'a']
	DG.add_n(c)
	node_list = DG.nodes()
	assert DG.most_important(2, node_list) == ['c', 'b'] #sorts alphabetically, but remember we use reverse=True to sort by numerical importance so the alphabetical sort is reversed too
	DG.add_n(d)
	node_list = DG.nodes()
	assert DG.most_important(1, node_list) == ['d']
	assert DG.most_important(2, node_list) == ['d', 'c']
	assert DG.most_important(3, node_list) == ['d', 'c', 'b']
	
	#testing sort by weighted importance of neighbors when node's own importance is a tie
	DG = nx.DiGraph()
	DG.add_n(a)
	DG.add_n(b)
	DG.add_n(c)
	DG.add_n(d)
	DG.add_edges_from([
			['a', 'c'], ['d', 'b']	#d is a more important neighbor than a, so b should be more important than c
	])
	node_list = ['b', 'c']
	assert DG.most_important(2, node_list) == ['b', 'c']

	DG = nx.DiGraph()
	DG.add_n(a)
	DG.add_n(b)
	DG.add_n(c)
	DG.add_n(d)
	DG.add_edges_from([
			['c', 'a'], ['b', 'd']
	])
	node_list = ['b', 'c']
	assert DG.most_important(2, node_list) == ['b', 'c']

	DG = nx.DiGraph()
	DG.add_n(a)
	DG.add_n(b)
	DG.add_n(c)
	DG.add_n(d)
	DG.add_edges_from([
			['c', 'a'], ['d', 'b']
	])
	node_list = ['b', 'c']
	assert DG.most_important(2, node_list) == ['b', 'c']

	#remember that when the nodes being compared are neighbors with each other, we will get some shared common neighbors, although they have different distances to the two compared nodes
	DG = nx.DiGraph()
	DG.add_n(a)
	DG.add_n(b)
	DG.add_n(c)
	DG.add_n(d)
	DG.add_edge('b', 'c')
	assert DG.most_important(2, node_list) == ['c', 'b']
	
	DG = nx.DiGraph()
	DG.add_n(a)
	DG.add_n(b)
	DG.add_n(c)
	DG.add_n(d)
	DG.add_edges_from([
		['c', 'a'], ['d', 'b']
	])
	assert DG.most_important(2, node_list) == ['b', 'c']
