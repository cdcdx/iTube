-- ------------------------------------------------------------------------

-- 创建数据库
CREATE DATABASE dav_db CHARSET utf8mb4;
-- 分配用户权限
create user dav@'%' identified by 'dav@123';
grant all privileges on *.* to dav@'%' with grant option;
alter user dav@'%' identified with mysql_native_password by 'dav@123';
flush privileges;

-- 重复计数
SELECT code,COUNT(code) as count FROM dav_local GROUP BY code HAVING count > 1 ORDER BY count DESC;
-- 重复计数
SELECT file,COUNT(file) as count FROM dav_local GROUP BY file HAVING count > 1 ORDER BY count DESC;
-- 重复路径详情排序
SELECT code,CONCAT(path,'/',file) as pathfile,size,duration,aspectratio,resolution,created FROM dav_local a WHERE ((SELECT COUNT(*) FROM dav_local WHERE file = a.file) > 1) ORDER BY file DESC;
-- 创建时间排序
SELECT id,code,size,duration,aspectratio,resolution,created FROM dav_local ORDER BY created ASC;

-- 单位时间存储比
SELECT id,code,size,duration,aspectratio,resolution,created,round(size/1024,2) as sizeGB,round(size/duration,2) as calcSec FROM `dav_local` where round(size/1024,2) > 5 ORDER BY round(size/duration,2) DESC;

-- ------------------------------------------------------------------------

-- 本地信息表: local table
DROP TABLE IF EXISTS `dav_local`;
CREATE TABLE `dav_local`
(
    `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',

    -- 识别码
    `code`                  varchar(48)   DEFAULT ''    COMMENT '识别码',   -- XXX-000
    `name`                  varchar(1024) NOT NULL      COMMENT '标题',     -- XXX-000 xxxxxx
    -- 文件信息
    `path`                  varchar(256)  DEFAULT ''    COMMENT '路径',     -- /nfs/hd01/
    `file`                  varchar(1024) DEFAULT ''    COMMENT '文件',     -- XXX-000 xxxxxx.mp4
    `size`                  float(16)     DEFAULT 0.0   COMMENT '大小',     -- 999 MByte
    `created`               datetime      DEFAULT NULL  COMMENT '创建时间',
    `duration`              float(16)     DEFAULT 0.0   COMMENT '时长',     -- 888 Second
    `aspectratio`           float(16)     DEFAULT 0.0   COMMENT '宽高比',   -- 0.5625/0.75
    `resolution`            varchar(16)   DEFAULT ''    COMMENT '分辨率',   -- 1080 720
    `format`                varchar(32)   DEFAULT ''    COMMENT '格式',     -- mp4
    `fps`                   float(16)     DEFAULT 0.0   COMMENT '帧率',     -- 30 60
    `crc`                   varchar(32)   DEFAULT ''    COMMENT 'crc',     -- 3d91035d
    -- 标记信息
    `subtitle`              varchar(8)    DEFAULT NULL  COMMENT '字幕',    --  NULL/CN/JP/EN
    `grade`                 int(4)        DEFAULT 0     COMMENT '等级',    --  -2 luan2 / -1 luan / 0 ai / 1 youma / 2 aima / 11 wuma / 99 good
    -- 个人评论
    `score`                 int(4)        DEFAULT 0     COMMENT '评分',    --  -10~0~10
    `comment`               varchar(256)  DEFAULT ''    COMMENT '评论', 

    `status`                int           DEFAULT 0     COMMENT '状态',    -- 0 exist / 1 delete
    `created_time`          datetime      DEFAULT NOW() COMMENT '创建时间',
    `updated_time`          datetime      DEFAULT NULL  COMMENT '更新时间',
    PRIMARY KEY (`id`)  USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
-- ALTER TABLE dav_local ADD format varchar(32) DEFAULT '' COMMENT '格式' AFTER resolution;

-- 搜索表: search table
DROP TABLE IF EXISTS `dav_search`;
CREATE TABLE `dav_search`
(
    `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',

    `parid`                 int           DEFAULT 0     COMMENT '父级ID', -- 0 nothing / other
    `key`                   varchar(48)   DEFAULT ''    COMMENT '搜索关键词',
    `type`                  int           DEFAULT 0     COMMENT '关键词分类',  -- 0 system / 1 key / 2 girl / 3 series / 4 actor
    `count`                 int           DEFAULT 1     COMMENT '搜索次数', 

    `status`                int           DEFAULT 0     COMMENT '状态',    -- 0 exist / 1 delete
    `created_time`          datetime      DEFAULT NOW() COMMENT '创建时间',
    `updated_time`          datetime      DEFAULT NULL  COMMENT '更新时间',
    PRIMARY KEY (`id`)  USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- 关键字替换表: keyword table
DROP TABLE IF EXISTS `dav_keyword`;
CREATE TABLE `dav_keyword`
(
    `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',

    `old_key`               varchar(48)   DEFAULT ''    COMMENT '替换关键词',
    `new_key`               varchar(48)   DEFAULT ''    COMMENT '替换关键词',
    `count`                 int           DEFAULT 1     COMMENT '替换次数', 

    `status`                int           DEFAULT 0     COMMENT '状态',    -- 0 exist / 1 delete
    `created_time`          datetime      DEFAULT NOW() COMMENT '创建时间',
    `updated_time`          datetime      DEFAULT NULL  COMMENT '更新时间',
    PRIMARY KEY (`id`)  USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ------------------------------------------------------------------------

-- 任务表: missions table
DROP TABLE IF EXISTS `dav_missions`;
CREATE TABLE `dav_missions`
(
    `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',

    `localid`               int           DEFAULT 0     COMMENT '文件ID', 
    -- 文件信息
    `path`                  varchar(512)  DEFAULT ''    COMMENT '路径',    -- /nfs/hd01/
    `file`                  varchar(512)  DEFAULT ''    COMMENT '文件',    -- XXX-000 xxxxxx.mp4
    -- 任务信息
    `type`                  int           DEFAULT 0     COMMENT '任务类型',  -- 0 null / 1 cut / 2 transcode / 3 scan_path / 4 clear_local_db
    -- 1 cut
    `start`                 int           DEFAULT 0     COMMENT '开始秒数', 
    `end`                   int           DEFAULT 0     COMMENT '结束秒数', 
    -- 2 transcode
    `preset`                varchar(16)   DEFAULT 'slow' COMMENT '编码速度',  -- ultrafast superfast veryfast faster fast medium slow slower veryslow
    `crf`                   int           DEFAULT 15     COMMENT '质量',    -- 0无损 23默认 51最差
    -- -- 3 scan
    -- `paths`                 varchar(512)  DEFAULT ''    COMMENT '路径',
    
    `status`                int           DEFAULT 0     COMMENT '状态',    -- 0 create / 1 doing / 2 done / -1 failed
    `created_time`          datetime      DEFAULT NOW() COMMENT '创建时间',
    `updated_time`          datetime      DEFAULT NULL  COMMENT '更新时间',
    PRIMARY KEY (`id`)  USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ntsc 720x480 / pal 720x576 / sntsc 640x480 / spal 768x576 / cif 352x288 / vga 640x480 / hd480 852x480 / hd720 1280x720 / hd1080 1920x1080 / 2k 2048x1080 / 4k 4096x2160
-- ------------------------------------------------------------------------

-- 网络信息表: web_info table
DROP TABLE IF EXISTS `dav_web`;
CREATE TABLE `dav_web`
(
    `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',

    -- 识别码
    `code`                  varchar(48)   NOT NULL      COMMENT '识别码',   -- XXX-000
    `name`                  varchar(1024) NOT NULL      COMMENT '标题',     -- XXX-000 xxxxxx
    -- 识别码信息
    `date`                  varchar(16)   DEFAULT ''    COMMENT '发行日期', 
    `studio`                varchar(64)   DEFAULT ''    COMMENT '发行商',  -- 
    `director`              varchar(64)   DEFAULT ''    COMMENT '导演',    -- 
    `series`                varchar(256)  DEFAULT ''    COMMENT '系列', 
    `genre`                 varchar(256)  DEFAULT ''    COMMENT '类别',   -- [ 1, 2 ]
    `actors`                varchar(256)  DEFAULT ''    COMMENT '演员',   -- [ 1, 2 ]
    `websites`              varchar(512)  DEFAULT ''    COMMENT '网站',   -- { "javbus": "", "javdb": "", "javlibrary": "", }
    `videos`                varchar(1024) DEFAULT ''    COMMENT '预览视频',   -- [ "https://", ]
    `images`                varchar(1024) DEFAULT ''    COMMENT '预览图片',   -- [ "https://", ]
    `magnet`                varchar(128)  DEFAULT ''    COMMENT '磁力链接',   -- [ "magnet://", ]
    -- 个人评论
    `score`                 int(4)        DEFAULT 0     COMMENT '评分',    --  -10~0~10
    `comment`               varchar(256)  DEFAULT ''    COMMENT '评论', 

    `status`                int           DEFAULT 0     COMMENT '状态',    -- 0 exist / 1 delete
    `created_time`         datetime      DEFAULT NOW() COMMENT '创建时间',
    `updated_time`         datetime      DEFAULT NULL  COMMENT '更新时间',
    PRIMARY KEY (`id`)  USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ------------------------------------------------------------------------

-- 演员表
DROP TABLE IF EXISTS `dav_actor`;
CREATE TABLE `dav_actor`
(
    `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',

    `name`                  varchar(48)   NOT NULL      COMMENT '演员', 
    `explain`               varchar(256)  DEFAULT ''    COMMENT '说明', 

    -- 演员信息
    `website`               varchar(512)  DEFAULT ''    COMMENT '网站',   -- { "javbus": "", "javdb": "", "javlibrary": "", }
    `avatar`                varchar(256)  DEFAULT ''    COMMENT '头像', 
    `debutdate`             varchar(16)   DEFAULT ''    COMMENT '出道日期', 

    -- CC
    `comment`               varchar(256)  DEFAULT ''    COMMENT '评论', 
    `score`                 int(4)        DEFAULT 0     COMMENT '评分', 

    `created_time`         datetime      DEFAULT NOW() COMMENT '创建时间',
    `updated_time`         datetime      DEFAULT NULL  COMMENT '更新时间',
    PRIMARY KEY (`id`)  USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- 类别表
DROP TABLE IF EXISTS `dav_category`;
CREATE TABLE `dav_category`
(
    `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',

    `name`                  varchar(48)   NOT NULL      COMMENT '类别', 
    `explain`               varchar(256)  DEFAULT ''    COMMENT '说明', 

    -- 类别信息
    `website`               varchar(512)  DEFAULT ''    COMMENT '网站',   -- [ "https://", ]

    -- CC
    `comment`               varchar(256)  DEFAULT ''    COMMENT '评论', 
    `score`                 int(4)        DEFAULT 0     COMMENT '评分', 

    `created_time`         datetime      DEFAULT NOW() COMMENT '创建时间',
    `updated_time`         datetime      DEFAULT NULL  COMMENT '更新时间',
    PRIMARY KEY (`id`)  USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- 识别码表
DROP TABLE IF EXISTS `dav_code`;
CREATE TABLE `dav_code`
(
    `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',

    `code`                  varchar(48)   NOT NULL      COMMENT '识别码',   -- XXX-
    `name`                  varchar(48)   NOT NULL      COMMENT '类别', 
    `explain`               varchar(256)  DEFAULT ''    COMMENT '说明', 

    -- 识别码信息
    `website`               varchar(512)  DEFAULT ''    COMMENT '网站',   -- [ "https://", ]

    -- CC
    `comment`               varchar(256)  DEFAULT ''    COMMENT '评论', 
    `score`                 int(4)        DEFAULT 0     COMMENT '评分', 

    `created_time`         datetime      DEFAULT NOW() COMMENT '创建时间',
    `updated_time`         datetime      DEFAULT NULL  COMMENT '更新时间',
    PRIMARY KEY (`id`)  USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ------------------------------------------------------------------------
