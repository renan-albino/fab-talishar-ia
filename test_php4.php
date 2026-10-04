<?php
 = file_get_contents(decks/teklovossen.json);
 = json_decode();
 = ->{cards};
 = false;
 = false;
 = [];
function GetCardId(, , , ) {
  if () { return 1; } elseif () { return 2; } elseif (isset(->{identifier})) { return str_replace(-, _, ->{identifier}); } return ";
}

