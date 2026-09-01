<?php

include_once "EncounterAI.php";

function CombatDummyAI()
{
  // Python bot_client.py handles all AI actions over HTTP/WebSockets
  return;
}

if (!function_exists('IsPlayerAI')) {
	function IsPlayerAI($playerID) {
		return false;
	}
}
