var window_UUID = makeid(50);
// var in_socket = io.connect('http://' + document.domain + ':' + location.port + "/" + window_UUID);
var out_socket = io.connect('http://' + document.domain + ':' + location.port);
console.log('http://' + document.domain + ':' + location.port)

function update_console(message){
  var element = document.getElementById("message_console")
  element.innerHTML = message;
  // var br = document.createElement("br");
  // var node = document.createTextNode (message);
  // element.appendChild(br);
  // element.appendChild(node);
}

// called in html
function init_plotter(){
  console.log('Initializing plotter.')
  out_socket.emit('init_plotter', {
    'window_UUID':window_UUID
  });
}

function start_full(){
  console.log('Starting full scan.')
  out_socket.emit('start_full', {
    'window_UUID':window_UUID
  });
}
function stop_full(){
  console.log('Stopping full scan.')
  out_socket.emit('stop_full', {
    'window_UUID':window_UUID
  });
}

function ping(){
  console.log('Requesting scans...')
  out_socket.emit('ping', {
    'window_UUID':window_UUID
  });
}

out_socket.on( 'status_update', function( msg ) {
  var message = JSON.parse(msg)['status']
  console.log(message)
  update_console(message)

})

out_socket.on( 'command', function( msg ) {
  var message = JSON.parse(msg)['command']
  console.log(message)
  update_console('reloading')
  if(message.localeCompare('reload') == 0){
    location.reload(true);
    return false
  }

})

function rr(){
  location.reload();
  return false
}
