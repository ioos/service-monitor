function initHelpJS() {
    $('.expandable').click(function(e) {
        deselectAll();
        console.log("Clicked");
        console.log($(e.target));
        if($(e.target).prop('tagName') == 'A') {
            toggleItem(e.target);
        } else if($(e.target).prop('tagName') == 'H4') {
            toggleItem($(e.target).parent());
        }
    });
}

function toggleItem(item) {
    console.log(item);
    $('#' + $(item).attr('data-id')).toggleClass('toggle-hide');
    $(item).toggleClass('active');
}

function deselectAll() {
    var active = $('.list-group').find('.active');
    active.each(function(i, v) { return toggleItem(v); });
}

