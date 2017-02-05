import $ from 'jquery'
import Bloodhound from 'bloodhound-js'

const SEARCH_URL = 'https://search.helpmanual.io/{query}'
// const SEARCH_URL = 'http://localhost:5000/{query}'

let search_source = new Bloodhound({
  datumTokenizer: Bloodhound.tokenizers.whitespace,
  queryTokenizer: Bloodhound.tokenizers.whitespace,
  remote: {
    url: SEARCH_URL,
    wildcard: '{query}'
  }
})

const EMPTY = '<div class="no-results">No results found</div>'
let $spinner = $('#spinner')
let $index = $('#index-content')

$('#search').typeahead({
  minLength: 2
}, {
  source: search_source,
  display: 'name',
  limit: 20,
  templates: {
    empty: EMPTY,
    suggestion: function(v) {
      return `<div>
  <div>
    <span class="tag">${v.src}</span>
    <b>${v.name}</b>
  </div>
  <small>
    ${v.description}
  </small>
</div>`
    }
  }
}).on('typeahead:select', function(ev, suggestion) {
  window.location = suggestion.uri
}).on('typeahead:asyncrequest', function() {
  $spinner.show()
}).on('typeahead:asynccancel typeahead:asyncreceive', function() {
  $spinner.hide()
}).on('typeahead:active', function() {
  $index.fadeOut()
}).on('typeahead:idle', function() {
  $index.fadeIn()
})

$('.navbar .container').show()

// affix extra header
let $alt_head = $('#alt-head')
let head_limit = 70
let alt_head_shown = false
if (window.pageYOffset > head_limit) {
  $alt_head.show()
  alt_head_shown = true
}

window.onscroll = function() {
  if(window.pageYOffset > head_limit){
    if (!alt_head_shown) {
      $alt_head.fadeIn(200)
      alt_head_shown = true
    }
  } else {
    if (alt_head_shown) {
      $alt_head.fadeOut(200)
      alt_head_shown = false
    }
  }
};
