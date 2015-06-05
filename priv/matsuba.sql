CREATE TABLE board_filetypes (
  boardid INTEGER NOT NULL,
  typeid INTEGER NOT NULL,
  allow_new INTEGER NOT NULL DEFAULT 1,
  allow_reply INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (boardid, typeid)
);

CREATE TABLE boards (
  boardid INTEGER PRIMARY KEY,
  "name" TEXT NOT NULL,
  title TEXT NOT NULL,
  max_filesize INTEGER DEFAULT NULL,
  max_pages INTEGER DEFAULT NULL,
  sage_replies INTEGER DEFAULT NULL,
  close_replies INTEGER DEFAULT NULL,
  template TEXT,
  TEXT_threads INTEGER DEFAULT NULL,
  forced_anon INTEGER DEFAULT NULL,
  anonymous TEXT,
  id_ruleset TEXT,
  host TEXT NOT NULL,
  post_seq INTEGER NOT NULL DEFAULT 0,
);

CREATE TABLE filetypes (
  typeid INTEGER PRIMARY KEY,
  extension TEXT NOT NULL,
  change_name INTEGER NOT NULL DEFAULT 1,
  force_thumb INTEGER NOT NULL DEFAULT 0,
  thumbnail TEXT,
  tn_width INTEGER NOT NULL DEFAULT 0,
  tn_height INTEGER NOT NULL DEFAULT 0,
);

CREATE TABLE posts (
  boardid INTEGER NOT NULL,
  threadid INTEGER NOT NULL,
  postid INTEGER NOT NULL,
  posttime INTEGER NOT NULL,
  sticky INTEGER NOT NULL DEFAULT 0,
  sage INTEGER NOT NULL,
  aborn INTEGER DEFAULT 0,
  "name" TEXT NOT NULL,
  idcode TEXT NOT NULL,
  ip TEXT NOT NULL,
  "password" TEXT NOT NULL,
  link TEXT NOT NULL,
  "subject" TEXT NOT NULL,
  message TEXT NOT NULL,
  filename TEXT,
  "checksum" TEXT DEFAULT NULL,
  filesize INTEGER DEFAULT NULL,
  width INTEGER DEFAULT NULL,
  height INTEGER DEFAULT NULL,
  thumbnail TEXT,
  tn_width INTEGER DEFAULT NULL,
  tn_height INTEGER DEFAULT NULL,
  catnail TEXT,
  cat_width INTEGER DEFAULT NULL,
  cat_height INTEGER DEFAULT NULL,
  fileinfo TEXT,
  message_src TEXT,
  markup_style TEXT DEFAULT NULL,
  PRIMARY KEY (boardid, postid)
);

CREATE INDEX posts_checksum_idx ON posts (checksum);
CREATE INDEX posts_ip_idx ON posts (ip);

CREATE TABLE user_boards (
  userid INTEGER NOT NULL DEFAULT 0,
  boardid INTEGER NOT NULL DEFAULT 0,
  authority INTEGER DEFAULT NULL,
  PRIMARY KEY (userid, boardid)
);

CREATE TABLE users (
  userid INTEGER NOT NULL,
  securehash TEXT NOT NULL,
  authority INTEGER NOT NULL DEFAULT 0,
  capcode TEXT,
  loginname TEXT UNIQUE NOT NULL,
  lasthit INTEGER DEFAULT NULL,
  lastmark INTEGER NOT NULL DEFAULT 0,
  sessionkey TEXT DEFAULT NULL,
  PRIMARY KEY (userid)
);

CREATE TABLE bans (
  boardid INTEGER,
  banid INTEGER PRIMARY KEY,
  ip TEXT DEFAULT NULL,
  "name" TEXT NOT NULL,
  reason TEXT NOT NULL,
  bantime INTEGER NOT NULL DEFAULT 0,
  expires INTEGER DEFAULT NULL
);
