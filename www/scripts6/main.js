define( [
	"jquery",
	"underscore",
	"browser-detect",
	"check-types",
	"mathjax",
	"profile",
	"marked",
	"graph",
	"node",
	"graph-animation",
	"blinds",
	"chosen",
	"user",
	"mousetrap-extended",
	"vanilla-notify",
], function(
	$,
	_,
	browser,
	is,
	mathjax,
	undefined,
	marked,
	graph,
	Node,
	graphAnimation,
	Blinds,
	chosen,
	user,
	mousetrap,
	notify
){


///////////////////////// GLOBALS //////////////////////////
// expose some things as true globals, so i can access them from the JS console!
window.graph = graph
window.is = is
// window.user = user

let css_show_hide_array = ['#avatar', '#login-circle', '.logout-circle', '.see-preferences']
let show_hide_dict = {}
let circleClassConditions = {
	'bright-circle': node => node.learned,
	'axiom-circle': node => node.type === 'axiom' || node.type === null,
	'definition-circle': node => node.type === 'definition' || node.type === 'equivdefs',
	'theorem-circle': node => node.type === 'theorem' || node.type === 'example',
	'exercise-circle': node => node.type === 'exercise',
}
let repeatedly_updating_nodes = false

////////////////////// INITIALIZATION //////////////////////
let LOCAL_ID_PREFIX = $('body').attr('data-local-id-prefix')
window.LOCAL_ID_PREFIX = LOCAL_ID_PREFIX // for Node module.  could be passed in, but i'm lazy

let subjects = JSON.parse($('body').attr('data-subjects'))
let all_subjects = JSON.parse($('body').attr('data-all-subjects'))

let user_dict = JSON.parse($('body').attr('data-user-dict-json-string'))
log('user dict is...')
logj(user_dict)
if( is.emptyObject(user_dict) ){
	// not logged in:
	loginInit()
	show('#login')
}
else{
	// logged in:
		$(".display-name").html(user_dict["id_name"])
		$("#avatar").attr("src", user_dict["profile_pic"])
		hide('#login-circle')
	show('#overlay')
}
user.init(user_dict) // this should ALSO be triggered by jQuery when they login
let pref_blinds = new Blinds({
	window_id: 'preference-pane-blinds',
	expand_array: false,
	// render: // no render function needed, except maybe to process True, False, etc
	blind_class_conditions: {
		'pref-attribute': true,
		animated: user.prefs.animate_blinds,
		flipInX: user.prefs.animate_blinds,
	},
	read_mode_action: function(val, key){ user.setPref(key, val) },
})


graphAnimation.init({
	// window_id: 'graph-containter', // had to use 'body' // after animation actually works, put init inside $(document).ready() to guarantee that container was loaded first.  if that DOES NOT WORK, then respond to http://stackoverflow.com/questions/13865606/append-svg-canvas-to-element-other-than-body-using-d3 with that issue
	node_label: node => { if(node.type !== 'exercise') return node.gA_display_name }, // exercise names should NOT appear
	node_radius: function(node){
		let val = is.number(node.attrs['importance'].value)? node.attrs['importance'].value: 5
		return 7.9 * Math.sqrt(val)
	},
	circle_class_conditions: circleClassConditions,
	circle_events: { // this will not update if the user changes their preferences.  maybe we can hand graph-animation the user, and then it can access the prefs itself
		mouseover: node => { if( user.prefs.show_description_on_hover ) node.gA_display_name = node.attrs.description.value },
		mouseout: node => { if( user.prefs.show_description_on_hover ) node.gA_display_name = node.display_name },
	},
})
show('svg') // both svg and node-template are hidden on load
show('#banner')

let node_blinds = new Blinds({
	open_blind_default_state: user.prefs.open_node_default_state,
	window_id: 'node-template-blinds',
	keys: ['type', 'preamble', 'number', 'name', 'description', 'synonyms', 'plurals', 'notes', 'intuitions', 'examples', 'counterexamples', 'proofs', 'dependency_name_and_ids'], // if you change this, you may also need to edit the Node.key_list method.
	expand_array: true,
	collapse_array_keys: ['dependency_name_and_ids', 'synonyms', 'plurals'],
	append_keys: ['name', 'description', 'synonyms', 'plurals', 'notes', 'intuitions', 'examples', 'counterexamples', 'proofs', 'dependency_name_and_ids'], // but remember, expand_arrays always have an append key (this excludes dependencies)
	render: render_content,
	post_render: post_render_action,
	read_mode_action: save_node,
	transform_key: nodeKeyToDisplayKey,
	blind_class_conditions: {
		'node-attribute': true,
		animated: user.prefs.animate_blinds,
		flipInX: user.prefs.animate_blinds,
		empty: (node, display_key, key) => is.null(node[key]) || (is.array(node[key]) && (is.emptyArray(node[key]) || is.emptyString(node[key][0]))),
	},
	chosen: true,
})


let current_node = {}
$('#toggle-learn-state').click(function(){
	current_node.learned = !current_node.learned
	updateNodeTemplateLearnedState()
	graphAnimation.update()
})
function updateNodeTemplateLearnedState(){
	if( current_node.learned ){
		$('#toggle-learn-state').html('<img src="images/light-on.png">learned!')
	}else{
		$('#toggle-learn-state').html('<img src="images/light-off.png">not learned')
	}
}
$('#discard-node').click(function(){
	// remove node from our graph
	graph.removeNode(current_node)
	graphAnimation.update() // we should NOT need this
	// change view back to the graph
	fromBlindsToGraphAnimation()
	// tell server (maybe server wants to avoid sending this node over again) to discard-node too
	ws.jsend({command: 'discard-node', node_id: current_node.id})
})
$('#get-link').click(function(){
	let node_id = current_node.id
	let url = host+"?nodeid="+node_id
	copyToClipboard(url)
	notify.info({
		text: url,
		details: '<br>The link above was automatically copied to your clipboard, unless you have an older browser.',
	})
})
$('#print').click(function(){
	print_node(current_node)
})


let host = $('body').attr('data-host')
let ws = ('WebSocket' in window)? new WebSocket("ws://"+host+"/websocket"): undefined;
if( !def(ws) ) die('Your browser does not support websockets, which are essential for this program.')

ws.jsend = function(raw_object) {
	$.extend(raw_object, {identifier: user.get_identifier(), client_node_ids: graph.nodeIdsList()})
	ws.send(JSON.stringify(raw_object))
}
ws.onclose = function() {
	notify.warning({
		text: 'You are disconnected from the server.  Any changes you make at this time will not be saved.',
	})
}
ws.onopen = function() {
	let requested_id = $('body').attr('data-requested-id')
	ws.jsend({command: 'first-steps', requested_id: requested_id})
	// if( is.nonEmptyString(requested_id) ){

	// TEMP
	// guestLogin()
	// promptStartingNodes()
	// addNode()
	// ws.jsend({ command: 'search', search_term: 'dual' })

	repeatedlyUpdateNodes()
}
ws.onmessage = function(event) { // i don't think this is hoisted since its a variable definition. i want this below graphAnimation.init() to make sure that's initialized first
	let ball = JSON.parse(event.data)
	window.ball = ball
	// logj('got message: ', ball)
	if( ball.command === 'populate-oauth-urls' ) {
		oauth_url_dict = ball.url_dict
	}
	else if( ball.command === 'update-user' ){
		user.update_identifier(ball['identifier'])
	}
	else if( ball.command === 'load-user' ) {
		user.init(ball.user_dict)
		hide('#login')
		show('#overlay')
	}
	else if( ball.command === 'prompt-starting-nodes' ){
		// promptStartingNodes(subjects) // but not before x'ing out the login :(
	}
	else if( ball.command === 'open-node' ) {
		let node_id = ball.node_id
		openNode(node_id)
	}
	else if( ball.command === 'load-graph' ) {
		let raw_graph = ball.new_graph

		raw_graph.nodes = _.map(raw_graph.nodes, raw_node => new Node(raw_node))

		let ready_graph = raw_graph
		window.ready_graph = ready_graph
		graph.addNodesAndLinks({
			nodes: ready_graph.nodes,
			links: ready_graph.links,
		})

		// TEMP
		// openNode('factorial')
		// ws.jsend({command: 'get-goal-suggestion'})
	}
	else if( ball.command === 'remove-edges' ) {
		graph.removeLinks({
			node_id: ball.node_id,
			dependency_ids: ball.dependency_ids,
		})
	}
	else if( ball.command === 'display-error' ) {
		let errorMessage = 'Server-Side Error: ' + ball.message
		notify.error({
			text: errorMessage,
		})
	}
	else if(ball.command === 'search-results'){
		populate_search_results(ball.results)
	}
	else if (ball.command === 'suggest-goal') {
		let goal = new Node(ball.goal)
		if (user.prefs.always_accept_suggested_goal) {
			$.event.trigger({
				type: 'accept-goal',
				message: goal.id,
			})
		}
		else{
			let details = goal.description
			let message = 'The goal "' + goal.name + '" has been suggested.  Would you like to accept the goal?'
			notify.info({
				text: message,
				buttons: [
					{
						text: 'yes',
						action: function(){$.event.trigger({type: 'accept-goal', message: goal.id})},
					},
					{
						text: 'no',
					},
				],
				details: 'Details: "' + details + '"',
			})
		}
	}
	else if (ball.command === 'suggest-pregoal') {
		let pregoal = new Node(ball.pregoal)
		if (user.prefs.always_accept_suggested_pregoal) {
			$.event.trigger({
				type: 'accept-pregoal',
				message: pregoal.id,
			})
		}
		else{
			let details = pregoal.description
			let message = 'The pregoal "' + pregoal.name + '" has been suggested.  Would you like to accept the pregoal?'
			notify.info({
				text: message,
				buttons: [
					{
						text: 'yes',
						action: function(){$.event.trigger({type: 'accept-pregoal', message: pregoal.id})},
					},
					{
						text: 'no',
					},
				],
				details: 'Details: "' + details + '"',
			})
		}
	}
	else if (ball.command === 'highlight-goal') {
		let goal = new Node(ball.goal)
		notify.success({
			text: 'Your new goal is "' + goal.name + '"!!!!',
		})
	}
	else if (ball.command === 'change-node-id') {
		let old_id = ball.old_node_id
		let new_id = ball.new_node_id
		change_node_id(old_id, new_id)
	}
	else log('Unrecognized command '+ball.command+'.')
}

function repeatedlyUpdateNodes() {
	// update the nodes every "seconds" seconds
	let seconds = 30
	if( !repeatedly_updating_nodes ){ // to ensure idempotency
		setInterval(updateNodes, seconds * 1000)
		repeatedly_updating_nodes = true
	}
}
function updateNodes() {
	// needs user, graph, and ws to be defined
	ws.jsend({command: 'update-nodes'})
}


$(document).on('jsend', function(Event) {
	ws.jsend(Event.message)
})
$(document).on('add-links', function(Event) {
	graph.addNodesAndLinks({
		links: Event.message,
	})
})
$(document).on('request-node', function(Event) {
	ws.jsend({command: 'request-node', node_id: Event.message})
})
$(document).on('save-node', function(Event){
	// console.log('sending dict: '+JSON.stringify(current_node.dict()))
	let proposed_id = Event.message // this is undefined if no message exists
	let is_new = def(proposed_id)
	ws.jsend({ command: 'save-node', node_dict: current_node.dict(), is_new: is_new, proposed_id: proposed_id })
})
$(document).on('accept-goal', function(Event){
	ws.jsend({ command: "set-goal", goal_id: Event.message })
})
$(document).on('accept-pregoal', function(Event){
	ws.jsend({ command: "set-pregoal", pregoal_id: Event.message })
})
updateSearchResultsWrapperMaxHeight()
$(window).resize(updateSearchResultsWrapperMaxHeight)


//////////////////// LOGIN/LOGOUT STUFF ////////////////////
var oauth_url_dict = undefined

$('#x').click(guestLogin)
$('#login-circle').click(function() {
	hide('#overlay')
	show('#login')
})
$('#login-button').click(login)
$('.image-wrapper').click(function() {
	$('.image-wrapper').removeClass('invalid')
})
$('.logout-circle').click(function() {
	push_pull_drawer()
	logout()
})


function login() { // this is what runs when the user clicks "login"
	if( !def(oauth_url_dict) ) notify.error({ text: 'oauth login broken.' })
	let account_type = $('input[type=radio][name=provider]:checked').val()
	if( !def(account_type) || account_type === '' ){
		if( !def(account_type) ){
			$('.image-wrapper').addClass('invalid')
		}
		if( account_type === '' ){
			$('#social-icon-container > img').addClass('invalid')
		}
	} else {
		location.href = oauth_url_dict[account_type]
	}
}
function guestLogin() { // this is when user uses the temp account on hand
	hide('#login')
		hide('#avatar')
		hide('.logout-circle')
		hide('.see-preferences')
		show('#login-circle')
	show('#overlay')
}
function logout(){ // this is what runs when the user clicks "logout"
	delete_cookie()
	hide('#overlay')
	show('#login')
}

//////////////////////// SEARCH BAR ////////////////////////
$mousetrap('#search-box').bind('enter', function(){
	// empty the search results (in case there were old searches)
	$('#search-results-wrapper').empty()
	// perform a new search
	ws.jsend({ command: 'search', search_term: $('#search-box').val() })
})
$('#search-wrapper').click(function(){
	$('#search-box').focus()
})
mousetrap.bind(user.prefs.search_keycut, function(){
	$('#search-box').focus()
	return false // to prevent default
})
$('#search-box').focus(expand_search_wrapper)
$(document).click(function(event) { // click anywhere BUT the #search-wrapper
	if (!$(event.target).closest('#search-wrapper').length && !$(event.target).is('#search-wrapper')) {
		close_search()
	}
})

function expand_search_wrapper() {
	$('#search-wrapper').width('800px')
	// $('#search-wrapper').height('auto')
}
function collapse_search_wrapper() {
	$('#search-wrapper').width('300px')
	// $('#search-wrapper').height('50px')
}
function close_search() {
	$('#search-results-wrapper').empty()
	collapse_search_wrapper()
	// move focus off search, to make sure CSS will shrink it
	$('#search-box').blur()
}


/////////////////////// ACTION STUFF ///////////////////////
function preview_box_clicked(node_id){
	// 1. add the node to the actual graph (REQUEST node to get any needed edges)
	ws.jsend({command: 'request-node', node_id: node_id})
}
function node_in_preview_box_clicked(node_id){
	// get the node (in the FUTURE we should not actually put it on the GRAPH ANIMATION though)
	ws.jsend({command: 'request-node', node_id: node_id})
	// display node
	if( node_id in graph.nodes ){
		openNode(node_id)
	}
}
function node_in_preview_box_right_clicked(node, results){
	node.learned = !node.learned
	// update search results and graph animation visually
	$('#search-results-wrapper').empty()
	populate_search_results(results)
	graphAnimation.update()
}
function populate_search_results(results){
	let $search_results_wrapper = $('#search-results-wrapper')
	for( let result of results ){
		// if the node is in the graph, use that one.  otherwise, make it here.  This should be improved in the future.  There should be like a shared node pool of all nodes on hand, to eliminate redundancy.  This is an issue because users could overwrite one version of the node with another, etc.
		let node = new Node(result)
		if( node.id in graph.nodes ){
			node = graph.nodes[node.id]
		}
		let html = result_htmlified(node)
		$search_results_wrapper.append(html)
		// Bind a click event! This must be done AFTER the html element is created.
		let $result = $search_results_wrapper.children().last()
		$result.click(function(){
			preview_box_clicked(node.id)
		})
		let $nodecircle = $result.find('.preview-circle-wrapper > div')
		$nodecircle.click(function(){
			node_in_preview_box_clicked(node.id)
		})
		$nodecircle.on('contextmenu', function(Event){ // on right click
			Event.preventDefault() // don't show contextmenu
			node_in_preview_box_right_clicked(node, results)
		})
	}
}

mousetrap.bind(user.prefs.toggle_name_display_keycut, function(){
	user.prefs.display_number_instead_of_name = !user.prefs.display_number_instead_of_name
	graphAnimation.update()
	return false
})
mousetrap.bind('ctrl+i', function(){
	user.prefs.display_id_instead_of_name = !user.prefs.display_id_instead_of_name
	graphAnimation.update()
	return false
})
$('#avatar').click(push_pull_drawer)
$('#get-starting-nodes').click(promptStartingNodes)
mousetrap.bind(user.prefs.start_subject_keycut, function(){
	promptStartingNodes()
	return false
})
$('#get-goal-suggestion').click(function(){
	ws.jsend({command: 'get-goal-suggestion'})
})
$('#get-pregoal-suggestion').click(function(){
	ws.jsend({command: 'get-pregoal-suggestion'})
})
$('#push').click(function(){
	alert('pull')
})

$('#add-node').click(addNode)
mousetrap.bind(user.prefs.new_node_keycut, function(){
	// if a node is open, close (and save) it
	if( show_hide_dict['#node-template'] === 'visible' ){
		fromBlindsToGraphAnimation()
	}
	addNode()
	return false
})

function push_pull_drawer() {
	// detect if drawer is in or out
	let $display_name = $('.display-name')
	let $logout = $('.logout-circle')
	let $see_prefs = $('.see-preferences')
	let drawer_position = $logout.css('right')
	if( drawer_position === '0px' ){
		// pull drawer out
		$logout.addClass('logout-circle-out')
		$display_name.addClass('display-name-out')
		$see_prefs.addClass('see-preferences-out')
	}
	else if( drawer_position === '55px' ){
		// put drawer in
		$logout.removeClass('logout-circle-out')
		$display_name.removeClass('display-name-out')
		$see_prefs.removeClass('see-preferences-out')
	}
	else log('unexpected drawer position')
}

/////////////////////// TOGGLE STUFF ///////////////////////
$(document).on('node-click', function(Event){
	let node_id = Event.message
	openNode(node_id)
})
$(document).on('node-right-click', function(Event){
	let node_id = Event.message
	let node = graph.nodes[node_id]
	node.learned = !node.learned
	graphAnimation.update()
})
$('.see-preferences').click(seePreferences)
mousetrap.bind(user.prefs.prefs_keycut, function(){
	seePreferences()
	return false
})

$('.back').click(fromBlindsToGraphAnimation)
mousetrap.bindGlobal(user.prefs.back_keycut, function(){
	// if search bar is in focus, shrink it
	if( $('#search-box').is(':focus') ){
		close_search()
	}

	// if blinds are showing, hide them
	if( show_hide_dict['#node-template'] === 'visible' || show_hide_dict['#preference-pane'] === 'visible' ){
		fromBlindsToGraphAnimation()
	}
	// else if login screen is up, hide it / guest login
	else if( show_hide_dict['#login'] === 'visible' ){
		guestLogin()
	}
})
function fromBlindsToGraphAnimation(){
	if( user.prefs.animate_blinds ){
		$('.node-attribute').addClass('animated flipOutX')
		$('.node-attribute').one('webkitAnimationEnd mozAnimationEnd MSAnimationEnd oanimationend animationend', toggleToGraphAnimation)
		$('.pref-attribute').addClass('animated flipOutX')
		$('.pref-attribute').one('webkitAnimationEnd mozAnimationEnd MSAnimationEnd oanimationend animationend', toggleToGraphAnimation)
	}
	else toggleToGraphAnimation()
}
function toggleToGraphAnimation() {
	let please_close_node = false
	if( show_hide_dict['#node-template'] === 'visible' ){
		hide('#node-template')
		please_close_node = true
	}
	let please_close_prefs = false
	if( show_hide_dict['#preference-pane'] === 'visible' ){
		hide('#preference-pane')
		please_close_prefs = true
	}
	show('svg')
	show('#overlay')
	// figure out which blinds are open, and close that one (closing unopened blinds could have side-effects)
	if( please_close_node ) node_blinds.close()
	if( please_close_prefs ) pref_blinds.close()
}

////////////////////////// HELPERS /////////////////////////
function print_node(node) {
	let url = "print"+"?nodeid="+node.id // the url is relative
	let win = window.open(url)
	// the following is no good because it sometimes gets called before mathjax finishes its job.  mathjax runs async, so it's a race issue
	// win.print()
	// win.close()
}

function render_content(string) {
	if (typeof string !== "string") die('The inputted variable is NOT a string!  It has type ' + typeof string + '!  It looks like: ' + JSON.stringify(string))

	// strip garbage '<div>'s added by certain browsers (will not escape user typed '<div>'s which are HTML escaped and therefore purposeless)
	string = string.replace(/<div>/g, '')
	string = string.replace(/<\/div>/g, '')

	// run katex
	// string = string.replace(/\$[^\$]*\$/g, katexRenderIfPossible)
	// return string

	// run marked
	// make all \ into \\ instead, so that they will be \ again when marked is done. This is for MathJax postrender compatability.
	string = string.replace(/\\/g, '\\\\')
	string = marked(string)

	// change <img23> shortcuts to <img src="http://provemath.org/image/NUMBER.jpg"
	string = string.replace(/img(\d+)/g, '<img src="image/$1.jpg" />') // this is maybe NOT a good markup choice, since it is an HTML tag
	string = string.replace(/\\includegraphics\{(.*?)\}/g, '<img src="image/$1.jpg" />')

	return string
}

function post_render_action(idToEdit) {
	// See https://github.com/MareoRaft/prove-math/issues/37 for info.
	mathjax.Hub.Queue(['Typeset', mathjax.Hub, idToEdit])
}

function save_node(value, key, parent_object) {
	// retrieve the node
	let node = undefined
	if (is.instance(parent_object, Node)) {
		node = parent_object
	}
	else { // parent_object is usually an array in this case
		node = current_node
	}

	if (!is.assigned(node.id)) die('No node id.')
	if (node.id.startsWith(LOCAL_ID_PREFIX)) { // if it was a temp ID, update the id
		let proposed_id = reduce_string(node.name)
		if (is.emptyString(proposed_id)) {
			// pass.  do not update id.  do not save node.
			console.log('Cannot create a real ID yet.')
		}
		else {
			// attempt to save to server.  Server will pick an ID
			$.event.trigger({ type: 'save-node', message: proposed_id })
		}
	}

	// if the ID is not local, save it to the server (request-node will happen on the server side)
	if (!node.id.startsWith(LOCAL_ID_PREFIX)) {
		$.event.trigger({ type: 'save-node' })
	}

	// update the node (close and reopen node-template) if internal things have changed
	if( _.contains(['type', 'preamble'], key) ){
		node_blinds.close()
		openNode(node.id)
	}
}

function change_node_id(old_id, new_id) {
	// update id in graph
	if ( ! _.contains(graph.nodeIdsList(), old_id) ) die('That node isn\'t in the graph to begin with.')
	if ( _.contains(graph.nodeIdsList(), new_id) ) die('That id is already being used for another node!')

	// retrieve the node object
	let node = graph.nodes[old_id]

	// update id key in graph
	graph.nodes[new_id] = node
	delete graph.nodes[old_id]

	// update id in the node
	node._id = new_id

	// update id in the graph animation (but see below comment)
	graphAnimation.update()

	// but the problem is that the old id is still being used elsewhere in the program (like the graph animation).  We could force the user to give the node a name so that we update the ID BEFORE setting any dependencies.
	// if any nodes depend on this node, we have a problem
}

// NOTE: the below function was found on https://stackoverflow.com/questions/400212/how-do-i-copy-to-the-clipboard-in-javascript#6055620
// Copies a string to the clipboard. Must be called from within an
// event handler such as click. May return false if it failed, but
// this is not always possible. Browser support for Chrome 43+,
// Firefox 42+, Safari 10+, Edge and IE 10+.
// IE: The clipboard feature may be disabled by an administrator. By
// default a prompt is shown the first time the clipboard is
// used (per session).
function copyToClipboard(text) {
    if (window.clipboardData && window.clipboardData.setData) {
        // IE specific code path to prevent textarea being shown while dialog is visible.
        return clipboardData.setData("Text", text);

    } else if (document.queryCommandSupported && document.queryCommandSupported("copy")) {
        var textarea = document.createElement("textarea");
        textarea.textContent = text;
        textarea.style.position = "fixed";  // Prevent scrolling to bottom of page in MS Edge.
        document.body.appendChild(textarea);
        textarea.select();
        try {
            return document.execCommand("copy");  // Security exception may be thrown by some browsers.
        } catch (ex) {
            console.warn("Copy to clipboard failed.", ex);
            return false;
        } finally {
            document.body.removeChild(textarea);
        }
    }
}

function updateSearchResultsWrapperMaxHeight() {
	$('#search-results-wrapper').css('max-height', $(window).height() - 90)
}

function result_htmlified(node) {
	let classNames = getClassesFromClassConditions(circleClassConditions, node)
	let classString = classNames.join(' ')
	return '<div class="preview-box">'
			+ '<div class="preview-top-bar">'
				+ '<div class="preview-circle-wrapper">'
					+ '<div class="'+classString+'"></div>' // the circle itself
				+ '</div>'
				+ '<div class="preview-name">'+node.display_name+'</div>'
			+ '</div>'
			+ '<div class="preview-description">'
				+ node.description
			+ '</div>'
		+ '</div>'
}

function getClassesFromClassConditions(class_conditions, node) {
	let class_names = []
	for( let class_name in class_conditions ){
		let value = class_conditions[class_name]
		if( is.function(value) ){
			let bool_func = value
			if( bool_func(node) ) class_names.push(class_name)
		}
		else if( is.boolean(value) ){
			let bool = value
			if( bool ) class_names.push(class_name)
		}
	}
	return class_names
}

function addNode() {
	let new_node = new Node()
	// put user preamble into node
	new_node.preamble = user.prefs.custom_preamble
	// add to graph and optionally open
	graph.addNode(new_node)
	if( user.prefs.open_new_nodes ){
		let node_id = new_node.id
		openNode(node_id)
	}
}

function openNode(node_id) {
	current_node = graph.nodes[node_id]
	updateNodeTemplateLearnedState()
	setTimeout(function() { // see http://stackoverflow.com/questions/35138875/d3-dragging-event-does-not-terminate-in-firefox
		node_blinds.open({
			object: current_node,
			keys: current_node.key_list(true),
		})
		hide('svg')
		hide('#overlay')
		show('#node-template')
	}, 0);
	if( false /*mode !== 'learn'*/){
		ws.jsend({ command: "re-center-graph", central_node_id: current_node.id })
	}
}

function seePreferences() {
	pref_blinds.open({
		object: user.prefs,
	})
	hide('svg')
	hide('#overlay')
	show('#preference-pane')
}

function promptStartingNodes() {
	let subjects_clone = _.clone(subjects)
	let last_subject = subjects_clone.pop()
	let subjects_string = '"' + subjects_clone.join('", "') + '"' + ', or "' + last_subject + '"'
	// replyToStartingNodesPrompt('combinatorics'); return // DEVELOPMENT CONVENIENCE, TEMP
	let subject = notify.success({
		text: 'What subject would you like to learn? Type ' + subjects_string + '.',
		prompt: {
			action: replyToStartingNodesPrompt,
			placeholder: 'subject',
		},
	})
}

function replyToStartingNodesPrompt(subject) {
	let default_subject = 'a'
	if( !_.contains(all_subjects, subject) ) subject = default_subject
	ws.jsend({'command': 'get-starting-nodes', 'subject': subject})
}

function hide(css_selector) {
	let $selected = $(css_selector)
	if( !_.contains(css_show_hide_array, css_selector) ){
		$selected.css('height', '0')
		$selected.css('width', '0')
		$selected.css('overflow', 'hidden')
	}else{
		// $selected.addClass('hidden')
		$selected.css('visibility', 'hidden')
	}
	// record whats hidden
	show_hide_dict[css_selector] = 'hidden'
}
function show(css_selector) { // this stuff fails for svg when using .addClass, so we can just leave show and hide stuff in the JS.
	let $selected = $(css_selector)
	if( !_.contains(css_show_hide_array, css_selector) ){
		$selected.css('height', '100%')
		$selected.css('width', '100%')
		$selected.css('overflow', 'scroll')
	}else{
		// $selected.removeClass('hidden')
		$selected.css('visibility', 'visible')
	}
	// record whats visible
	show_hide_dict[css_selector] = 'visible'
}

function nodeKeyToDisplayKey(word, node) {
	if( word === 'description' ) return node.type
	if( word === 'dependency_name_and_ids' ) return 'dependencies'
	if( word === 'dependencies' || word === 'synonyms' || word === 'plurals' ) return word // we want these to stay plural
	if( word[word.length - 1] === 's' ) return word.substr(0, word.length - 1)
	return word // word may have ALREADY been singular
}

function loginInit() {
	$('#account-type').chosen({
		allow_single_deselect: true,
		inherit_select_classes: true,
		search_contains: true,
		width: '100%'
	}).change(function(){
		$('.account-type .chosen-single').removeClass('invalid')
	})
}

function delete_cookie() {
	document.cookie = 'mycookie=; expires=Thu, 01 Jan 1970 00:00:01 GMT;'
}


}) // end define
