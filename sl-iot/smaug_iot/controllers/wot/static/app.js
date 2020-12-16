var effectName = 'bounce';

function result (code, type, status, data) {
    $('#code').text(code).effect(effectName);
    $('#type').text(type).effect(effectName);
    $('#status').text(status).effect(effectName);
    $('#result').text(data);
}

function action(url, method) {
    var token = $('#bearer-token').val();
    console.log("action", url, method, token);

    $('#url').text(url).effect(effectName);
    $('#method').text(method).effect(effectName);

    $.ajax({
        "url": url,
        "method": method,
        "headers": {"Authorization": "Bearer " + token},
        "success": function(data, status, xhr) { result(xhr.status, "success", status, data); },
        "error": function(xhr, error) { result(xhr.status, "error", error, ""); }
    });
}

$('.token-setter').click(
    function(event) {
        event.preventDefault();
        $('#bearer-token').val($(this).data('token'));
    });

$('#action-status').click(function() {
    action("/api/status", "GET");
});
$('#action-lock').click(function() {
    action("/api/action/lock", "POST");
});
$('#action-unlock').click(function() {
    action("/api/action/unlock", "POST");
});
