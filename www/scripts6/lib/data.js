define( ['jquery', 'underscore', 'check-types', 'profile', 'd3-and-svg'], function($, _, check, undefined, d3AndSVG) {


/////////////////////////////////// HELPERS ///////////////////////////////////
function removeParenthesizedThing(string){
	return string.replace(/\([^\)]*\)/, '')
}

function removeOneContextFromNames(){
	// go through nodes and update the displayNames to be the _names with removal (above function)
	_.each(d3AndSVG.nodes, function(node){
		node.displayName = removeParenthesizedThing( node._name )
	})
	// after the loop is completed, kickoff the d3 restart, which should trigger the UPDATE automatically
	d3AndSVG.processNewGraph() // nodes and links variables are global
}

function showFullContextInNames(){
	_.each(d3AndSVG.nodes, function(node){
		node.displayName = node._name
	})
	d3AndSVG.processNewGraph()
}



///////////////////////////////// NODE THINGS /////////////////////////////////
function removeNodeById(id){ // assumes only one node of each id exists
	check.assert.string(id)
	for( let i in d3AndSVG.nodes )if( d3AndSVG.nodes[i]._id === id ){
		d3AndSVG.nodes.splice(i, 1)
		return true
	}
	die('No node of that id to remove.')
}

function removeLinksFromArrayById(link_array, id){
	check.assert.array.of.object(link_array)
	check.assert.string(id)
	for( let i = 0; i < link_array.length; i++ )if( link_array[i].source._id === id || link_array[i].target._id === id ){
		link_array.splice(i, 1)
		i--
	}
	return link_array
}

function removeLinksById(id){
	d3AndSVG.links = removeLinksFromArrayById(d3AndSVG.links, id)
}

function findObjectById(array, id){
	check.assert.array(array)
	check.assert.string(id)
	for( let i in array )if( array[i]._id === id ) return array[i]
	die('id not found.')
}

function addNewNodes(new_nodes) {
	_.each(new_nodes, function(new_node){
		new_node.displayName = new_node._name
	})
	d3AndSVG.nodes.pushArray(new_nodes)
	check.assert.array.of.object(d3AndSVG.nodes)
}

function updateNodesAndLinks(new_graph) {
	//if a node is marked 'remove', remove it from nodes, new_graph.nodes, and links
	for( let i = 0; i < new_graph.nodes.length; i++ ){
		if( new_graph.nodes[i].empty ){
			// maybe replace it with a minimal dict and some message "please complete me!"
			console.log('Found an empty node. Letting it proceed.')
		}
		else if( new_graph.nodes[i].remove ){
			removeNodeById(new_graph.nodes[i]._id)
			removeLinksById(new_graph.nodes[i]._id) // we assume there are no links to a removed node in new_graph.links.  That is, we assume a good input.
			new_graph.nodes.splice(i, 1)
			i--
		}
		// if( id already exists )... // d3 won't duplicate an element, so we're ok here.  But a good input should probably not send over the same element again anyway...
	}

	addNewNodes(new_graph.nodes)

	//update source and targets of links to point to objects, not IDs
	_.each(new_graph.links, function(link){
		link.source = findObjectById(d3AndSVG.nodes, link.source)
		link.target = findObjectById(d3AndSVG.nodes, link.target)
	})
	d3AndSVG.links.pushArray(new_graph.links)
	check.assert.array.of.object(d3AndSVG.links)

	d3AndSVG.processNewGraph(new_graph)
}

//////////////////////////////////// MAIN /////////////////////////////////////
return {
	updateNodesAndLinks: updateNodesAndLinks,
	removeOneContextFromNames: removeOneContextFromNames,
	showFullContextInNames: showFullContextInNames,
}


}); // end of define
