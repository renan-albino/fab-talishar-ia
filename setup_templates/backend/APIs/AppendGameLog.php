<?php
include '../Libraries/HTTPLibraries.php';
SetHeaders();

$postData = json_decode(file_get_contents('php://input'), true) ?: $_POST;
$gameName = $postData['gameName'] ?? ($_GET['gameName'] ?? '');
$message = $postData['message'] ?? ($_GET['message'] ?? '');

if (!$gameName || !$message) {
  echo json_encode(['error' => 'Missing gameName or message']);
  exit;
}

$filename = '../Games/' . basename($gameName) . '/gamelog.txt';
if (file_exists(dirname($filename))) {
  @file_put_contents($filename, $message . "\r\n", FILE_APPEND);
  echo json_encode(['status' => 'OK']);
} else {
  echo json_encode(['error' => 'Game not found']);
}

