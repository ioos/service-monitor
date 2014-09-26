function initHelpJS() {
    $('.expandable').click(function(e) {
        e.preventDefault();
        if($(e.target).prop('tagName') == 'A') {
            if($(e.target).hasClass('active')) {
                deselectAll();
            } else {
                deselectAll();
                toggleItem(e.target);
            }
        } else if($(e.target).prop('tagName') == 'H4') {
            if($(e.target).parent().hasClass('active')) {
                deselectAll();
            } else { 
                deselectAll();
                toggleItem($(e.target).parent());
            }
        }
    });
}

function toggleItem(item) {
    $('#' + $(item).attr('data-id')).toggleClass('toggle-hide');
    $(item).toggleClass('active');
}

function deselectAll() {
    var active = $('.list-group').find('.active');
    active.each(function(i, v) { return toggleItem(v); });
}

