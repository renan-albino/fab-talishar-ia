<?php

include "../HostFiles/Redirector.php";
include "../Libraries/HTTPLibraries.php";
include_once "../Libraries/SHMOPLibraries.php";
include_once "../Libraries/PlayerSettings.php";
include_once '../Assets/patreon-php-master/src/PatreonDictionary.php';
require_once '../Assets/patreon-php-master/src/API.php';
include_once '../Assets/patreon-php-master/src/PatreonLibraries.php';
include_once "../AccountFiles/AccountDatabaseAPI.php";
include_once '../includes/functions.inc.php';
include_once '../includes/dbh.inc.php';
include_once '../Database/ConnectionManager.php';
SetHeaders();

$response = new stdClass();

$_POST = json_decode(file_get_contents('php://input'), true);
$deck = TryPOST("deck"); //This is for limited game modes (see JoinGameInput.php)
$decklink = TryPOST("fabdb"); //Deck builder decklink (any deckbuilder, name comes from when fabdb was the only one)
$deckTestMode = TryPOST("deckTestMode", ""); //If this is populated with ANYTHING, will start a game against the combat dummy
$format = TryPOST("format"); //Format of the game -- see function FormatCode for enum of formats
$visibility = TryPOST("visibility"); //"public" = public game, "private" = private game
$decksToTry = TryPOST("decksToTry"); //This is only used if there's no favorite deck or decklink. 1 = ira
$favoriteDeck = TryPOST("favoriteDeck", false); //Set this to true to save the provided deck link to your favorites
$favoriteDeckLink = TryPOST("favoriteDecks", "0"); //This one is kind of weird. It's the favorite deck index, then the string "<fav>" then the favorite deck link
$gameDescription = htmlspecialchars(TryPOST("gameDescription", "Game #"), ENT_QUOTES); //Just a string with the game name
$deckbuilderID = TryPOST("user", "");
$deckTestDeck = TryPOST("deckTestDeck", "");

if ($favoriteDeckLink != 0) {
  $favDeckArr = explode("<fav>", $favoriteDeckLink);
  if (count($favDeckArr) == 1) $favoriteDeckLink = $favDeckArr[0];
  else {
    $favoriteDeckIndex = $favDeckArr[0];
    $favoriteDeckLink = $favDeckArr[1];
  }
}

session_start();

if (!isset($_SESSION["userid"])) {
  if (isset($_COOKIE["rememberMeToken"])) {
    loginFromCookie();
  }
}

$isShadowBanned = false;
if(isset($_SESSION["isBanned"])) $isShadowBanned = (intval($_SESSION["isBanned"]) == 1 ? true : false);
else if(isset($_SESSION["userid"])) $isShadowBanned = IsBanned($_SESSION["userid"]);
if(!$isShadowBanned) $isShadowBanned = IsIPBanned();

if ($visibility == "public" && $deckTestMode != "" && !isset($_SESSION["userid"])) {
  //Must be logged in to use matchmaking
  $response->error = "You must be logged in to create a public multiplayer game.";
  echo json_encode($response);
  exit;
}

if (isset($_SESSION["userid"])) {
  //Save game creation settings
  include_once '../includes/functions.inc.php';
  include_once '../includes/dbh.inc.php';
  if (isset($favoriteDeckIndex)) {
    ChangeSetting("", $SET_FavoriteDeckIndex, $favoriteDeckIndex, $_SESSION["userid"]);
  }
  ChangeSetting("", $SET_Format, FormatCode($format), $_SESSION["userid"]);
  $visibilitySetting = ($visibility == "public" ? 1 : ($visibility == "friends-only" ? 2 : 0));
  ChangeSetting("", $SET_GameVisibility, $visibilitySetting, $_SESSION["userid"]);
  if($deckbuilderID != "")
  {
    if(str_contains($decklink, "fabrary")) storeFabraryId($_SESSION["userid"], $deckbuilderID);
  }
}

session_write_close();

$gameName = GetGameCounter("../");


if ((!file_exists("../Games/$gameName")) && (mkdir("../Games/$gameName", 0777, true))) {
  chmod("../Games/$gameName", 0777);
} else {
  $response->error = "Game file could not be created.";
  echo (json_encode($response));
  exit;
}

if($isShadowBanned) {
  if($format == "cc" || $format == "futurecc" || $format == "llcc" || $format == "openformatllcc" || $format == "openformatsage") $format = "shadowcc";
  else if($format == "compcc") $format = "shadowcompcc";
  else if($format == "compllcc") $format = "shadowcompllcc";
  else if($format == "blitz" || $format == "commoner") $format = "shadowblitz";
  else if($format == "futuresage" || $format == "sage" || $format == "compsage") $format = "shadowcompsage";
  else if($format == "gage") $format = "shadowgage";
}

$p1Data = [1];
$p2Data = [2];
if ($deckTestMode != "") {
  $gameStatus = 4; // Ready to start
  $p2SideboardSubmitted = "1";
  $p2IsAI = "1";
  $firstPlayer = 1;
  $firstPlayerChooser = "1";

  $cleanOppSlug = basename($deckTestDeck, ".json");
  if (!$cleanOppSlug) $cleanOppSlug = "betsy";
  file_put_contents("../Games/" . $gameName . "/p2_bot_needed.txt", $cleanOppSlug);
  $oppJsonPaths = [
    dirname(__FILE__) . "/../decks/" . $cleanOppSlug . ".json",
    "../decks/" . $cleanOppSlug . ".json",
    "/var/www/html/game/decks/" . $cleanOppSlug . ".json",
    "../../decks/" . $cleanOppSlug . ".json",
    "../" . $cleanOppSlug . ".json"
  ];
  $oppLoaded = false;
  foreach ($oppJsonPaths as $op) {
    if (file_exists($op)) {
      $oppContent = json_decode(file_get_contents($op), true);
      if ($oppContent && isset($oppContent["cards"])) {
        $cardDb = [];
        $dbPaths = [
          dirname(__FILE__) . "/../data/fab_cards_db.json",
          "../data/fab_cards_db.json",
          "data/fab_cards_db.json",
          "/var/www/html/game/data/fab_cards_db.json"
        ];
        foreach ($dbPaths as $dbp) {
          if (file_exists($dbp)) {
            $cardDb = json_decode(file_get_contents($dbp), true) ?: [];
            break;
          }
        }

        $hero = "";
        $head = "";
        $chest = "";
        $arms = "";
        $legs = "";
        $weapons = [];
        $deckCards = [];
        $inv = [];

        foreach ($oppContent["cards"] as $c) {
          $cid = is_array($c) ? ($c["identifier"] ?? "") : strval($c);
          $qty = is_array($c) ? intval($c["total"] ?? 1) : 1;
          if (!$cid) continue;
          $meta = $cardDb[$cid] ?? [];
          $slot = $meta["slot"] ?? "Deck";
          $c_type = $meta["type"] ?? "";
          $subtype = $meta["subtype"] ?? "";

          if ($slot == "Hero" || $c_type == "H" || str_contains($subtype, "Hero")) {
            if (!$hero) $hero = $cid;
          } else if ($slot == "Head" || str_contains($subtype, "Head")) {
            if (!$head) $head = $cid;
            else $inv[] = $cid;
          } else if ($slot == "Chest" || str_contains($subtype, "Chest")) {
            if (!$chest) $chest = $cid;
            else $inv[] = $cid;
          } else if ($slot == "Arms" || str_contains($subtype, "Arms")) {
            if (!$arms) $arms = $cid;
            else $inv[] = $cid;
          } else if ($slot == "Legs" || str_contains($subtype, "Legs")) {
            if (!$legs) $legs = $cid;
            else $inv[] = $cid;
          } else if ($slot == "Weapon" || $slot == "Off-Hand" || $c_type == "W" || str_contains($subtype, "Weapon")) {
            if (count($weapons) < 2) $weapons[] = $cid;
            else $inv[] = $cid;
          } else {
            for ($q = 0; $q < $qty; ++$q) {
              $deckCards[] = $cid;
            }
          }
        }

        // Validate format minimum deck count (60 for CC, 40 for Blitz)
        $isCC = in_array(strtolower($format), ["cc", "compcc", "llcc", "compllcc", "futurecc", "futurell", "gage", "open_cc"]);
        $minCards = $isCC ? 60 : 40;
        if (count($deckCards) > $minCards) {
          $extra = array_slice($deckCards, $minCards);
          $deckCards = array_slice($deckCards, 0, $minCards);
          $inv = array_merge($inv, $extra);
        }

        if (!$hero) $hero = "ira_crimson_haze";
        $line1Parts = array_filter(array_merge([$hero], $weapons, [$head, $chest, $arms, $legs]));
        $line1 = implode(" ", $line1Parts);
        $line2 = implode(" ", $deckCards);

        $p2Lines = [
          $line1,
          $line2,
          "", "", "", "", "", "",
          implode(" ", $inv),
          "", "",
          implode(" ", $inv)
        ];

        file_put_contents("../Games/" . $gameName . "/p2Deck.txt", implode("\r\n", $p2Lines));
        $oppLoaded = true;
        break;
      }
    }
  }
  if (!$oppLoaded) {
    if ($deckTestDeck != "" && file_exists("../Assets/" . $deckTestDeck . ".txt")) {
      $opponentDeck = "../Assets/" . $deckTestDeck . ".txt";
    } else {
      $opponentDeck = "../Assets/Dummy.txt";
    }
    copy($opponentDeck, "../Games/" . $gameName . "/p2Deck.txt");
  }
} else {
  $gameStatus = 0; //Initial
  $p2SideboardSubmitted = "0";
  $p2IsAI = "0";
}
$firstPlayerChooser = "";
$firstPlayer = 1;
$p1Key = hash("sha256", rand() . rand());
$p2Key = hash("sha256", rand() . rand() . rand());
$p1uid = "-";
if($deckTestMode != "") $p2uid = "Practice Dummy";
else $p2uid = "-";
$p1DisplayName = "";
$p2DisplayName = "";
$p1id = "-";
$p2id = "-";
$hostIP = GetClientIP();
$gameGUID = GenerateGameGUID();

$filename = "../Games/" . $gameName . "/GameFile.txt";
$gameFileHandler = @fopen($filename, "w");
if ($gameFileHandler === false) {
  $response->error = "Game file could not be initialized.";
  echo json_encode($response);
  exit;
}
include "../MenuFiles/WriteGamefile.php";
WriteGameFile();

$filename = "../Games/" . $gameName . "/gamelog.txt";
$handler = @fopen($filename, "w");
if ($handler === false) {
  $response->error = "Game log could not be initialized.";
  echo json_encode($response);
  exit;
}
fclose($handler);
@chmod($filename, 0666);
@chmod("../Games/" . $gameName, 0777);

$currentTime = round(microtime(true) * 1000);
$cacheVisibility = ($visibility == "public" ? "1" : ($visibility == "friends-only" ? "2" : "0"));
WriteCache($gameName, 1 . "!" . $currentTime . "!" . $currentTime . "!0!-1!" . $currentTime . "!!!" . $cacheVisibility . "!0!0!0!" . FormatCode($format) . "!" . $gameStatus . "!0!0"); //Initialize SHMOP cache for this game

$playerID = 1;

include './JoinGame.php';
