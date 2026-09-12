<?php

include "../AccountFiles/AccountSessionAPI.php";
include_once '../includes/functions.inc.php';
include_once "../includes/dbh.inc.php";
include_once "../Libraries/PlayerSettings.php";
include_once "../Libraries/HTTPLibraries.php";
require_once '../Assets/patreon-php-master/src/PatreonLibraries.php';
include_once '../Assets/patreon-php-master/src/API.php';
include_once '../Assets/patreon-php-master/src/PatreonDictionary.php';

SetHeaders();

if (!IsUserLoggedIn()) {
  if (isset($_COOKIE["rememberMeToken"])) {
    loginFromCookie();
  }
}

$response = new stdClass();
$response->favoriteDecks = [];
$seenDeckSlugs = [];

if (IsUserLoggedIn()) {
  $savedSettings = LoadSavedSettings(LoggedInUser());
  $settingArray = [];
  $settingCount = count($savedSettings);
  for ($i = 0; $i < $settingCount; $i += 2) {
    $settingArray[$savedSettings[$i]] = $savedSettings[$i + 1];
  }

  $favoriteDecks = LoadFavoriteDecks(LoggedInUser());
  $favCount = count($favoriteDecks);
  if ($favCount > 0) {
    $selIndex = -1;
    if (isset($settingArray[$SET_FavoriteDeckIndex])) $selIndex = $settingArray[$SET_FavoriteDeckIndex];
    $response->lastUsedDeckIndex = $selIndex;
    for ($i = 0; $i < $favCount; $i += 7) {
      $deck = new stdClass();
      $deck->index = $i;
      $deck->key = $i . "<fav>" . $favoriteDecks[$i];
      $deck->name = $favoriteDecks[$i + 1];
      $deck->hero = $favoriteDecks[$i + 2];
      $deck->format = $favoriteDecks[$i + 3];
      $deck->cardBack = $favoriteDecks[$i + 4];
      $deck->playmat = $favoriteDecks[$i + 5];
      $deck->altArtsCustomized = boolval($favoriteDecks[$i + 6]);
      $deck->link = $favoriteDecks[$i];
      $response->favoriteDecks[] = $deck;
      $seenDeckSlugs[] = strtolower(basename($favoriteDecks[$i], ".json"));
    }
  }

  //Load other settings
  if (isset($settingArray[$SET_Format])) $response->lastFormat = FormatName($settingArray[$SET_Format]);
  if (isset($settingArray[$SET_GameVisibility])) $response->lastVisibility = $settingArray[$SET_GameVisibility];
}

// Injetar automaticamente todos os decks do diretório decks/ do Dashboard
$deckDirectories = array_filter([
  __DIR__ . "/../decks",
  __DIR__ . "/../../decks",
  "/var/www/html/decks",
  "/var/www/html/game/decks",
  getenv('PROJECT_ROOT') ? getenv('PROJECT_ROOT') . "/decks" : null,
]);

foreach ($deckDirectories as $deckDir) {
  if (is_dir($deckDir)) {
    $deckFiles = glob($deckDir . "/*.json");
    if ($deckFiles) {
      foreach ($deckFiles as $deckPath) {
        $slug = basename($deckPath, ".json");
        $slugLow = strtolower($slug);
        if (in_array($slugLow, $seenDeckSlugs)) continue;

        $content = @file_get_contents($deckPath);
        if (!$content) continue;
        $dObj = @json_decode($content, true);
        if (!$dObj) continue;

        $hero = $dObj["hero"] ?? "";
        if (empty($hero) && isset($dObj["cards"]) && is_array($dObj["cards"])) {
          foreach ($dObj["cards"] as $c) {
            $cid = is_array($c) ? ($c["identifier"] ?? "") : strval($c);
            $cidL = strtolower($cid);
            if (str_contains($cidL, "hero") || in_array($cidL, ["cindra", "betsy", "kassai", "dash", "vynnset", "hala", "jarl", "kayo", "rhinar", "dorinthea", "bravo", "victor", "gravy"])) {
              $hero = $cid;
              break;
            }
          }
          if (empty($hero) && count($dObj["cards"]) > 0) {
            $firstC = $dObj["cards"][0];
            $hero = is_array($firstC) ? ($firstC["identifier"] ?? "Hero") : strval($firstC);
          }
        }
        if (empty($hero)) $hero = "Hero";

        $idx = count($response->favoriteDecks) * 7;
        $deck = new stdClass();
        $deck->index = $idx;
        $deck->key = $idx . "<fav>" . $slug;
        $deckName = $dObj["name"] ?? ucwords(str_replace("_", " ", $slug));
        $deck->name = $deckName . " [Workspace]";
        $deck->hero = $hero;
        $deck->format = strtoupper($dObj["format"] ?? "CC");
        $deck->cardBack = "0";
        $deck->playmat = "0";
        $deck->altArtsCustomized = false;
        $deck->link = $slug;

        $response->favoriteDecks[] = $deck;
        $seenDeckSlugs[] = $slugLow;
      }
    }
    break;
  }
}

echo json_encode($response);
