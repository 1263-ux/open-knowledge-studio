/*!
 * Open Knowledge Studio — lunr 中文检索补丁
 *
 * 背景
 * ----
 * Just the Docs 的站内搜索建立在 lunr 之上，而 lunr 的分词完全是为英文设计的：
 *
 *   1. `lunr.tokenizer.separator` 默认只按空白/斜杠切分。一整段没有空格的
 *      中文会变成**一个超长词条**，「记忆召回机制」只有一个词条，
 *      只有把原文逐字原样输入才可能命中；
 *   2. `lunr.trimmer` 用 JS 的 `\W`（等价于 `[^A-Za-z0-9_]`）修剪词条首尾，
 *      而汉字恰好全部落在 `\W` 里，于是每个中文词条都被修剪成空字符串。
 *      中文内容实际上**从未进入过倒排索引**。
 *
 * 二者叠加的结果是：只要查询词含中文，命中数恒为 0。
 *
 * 做法
 * ----
 * 在浏览器端覆盖 lunr 的三个环节：
 *   - trimmer  → 保留中文字符，不再当作标点删除
 *   - stemmer  → Porter 词干化只对英文生效，中文原样放行
 *   - tokenizer→ 中文按「二元组（bigram）」切分，英文沿用「空白 / 斜杠」切分。
 *     其中只有偶数起点的二字组携带高亮位置，奇数起点的只参与匹配 ——
 *     否则 Just the Docs 的高亮拼接会把汉字重复输出（见 emitCjkRun 的注释）
 *
 * 中文为什么按二元组切：中文没有词边界，按单字切会让「召回」这类查询命中
 * 所有含「召」或「回」的页面（如「召开」），噪声太大；按二元组切则
 * 「召回」只会命中包含连续「召回」的页面，精度接近中文用户的心理预期，
 * 同时不需要引入词典或分词库（零依赖、不增加网络请求）。
 *
 * 放在浏览器端而不是构建期的原因：`search-data.json` 只存原始文本，
 * 真正的分词发生在 `index.add()` 与 `index.query()` 时。因此这里覆盖的函数
 * 对「建索引」和「查询」两侧同时生效，不必改动 Jekyll 构建流程，
 * 也不必把整份 search-data.json 重新生成为「已分词」格式。
 *
 * 已知取舍：单独输入一个汉字（如「库」）不会命中——索引里只有二元组。
 * 中文用户极少这样检索，且换来的是 2 字查询的高精度，因此接受。
 */
(function () {
  'use strict';

  if (typeof lunr === 'undefined') return;

  /* 需要单独分词的表意文字区段：假名、CJK 扩展 A、CJK 基本区、CJK 兼容区 */
  function isCjk(code) {
    return (
      (code >= 0x3040 && code <= 0x30ff) ||
      (code >= 0x3400 && code <= 0x4dbf) ||
      (code >= 0x4e00 && code <= 0x9fff) ||
      (code >= 0xf900 && code <= 0xfaff)
    );
  }

  var CJK = '\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff';
  /* 词条首尾要剥掉的字符：既不是 ASCII 字母数字下划线，也不是表意文字 */
  var TRIM_EDGE = new RegExp('^[^A-Za-z0-9_' + CJK + ']+|[^A-Za-z0-9_' + CJK + ']+$', 'g');
  var HAS_CJK = new RegExp('[' + CJK + ']');
  var IS_SEPARATOR = /[\s/]/;

  /* ------------------------------------------------------------------ *
   * 1) trimmer：不要再把汉字当标点删掉
   * ------------------------------------------------------------------ */
  lunr.trimmer = function (token) {
    return token.update(function (value) {
      return String(value).replace(TRIM_EDGE, '');
    });
  };

  /* ------------------------------------------------------------------ *
   * 2) stemmer：Porter 词干化只对英文有意义
   * ------------------------------------------------------------------ */
  var originalStemmer = lunr.stemmer;
  lunr.stemmer = function (token) {
    return HAS_CJK.test(String(token)) ? token : originalStemmer(token);
  };

  /* ------------------------------------------------------------------ *
   * 3) tokenizer：中文按二元组切分，英文沿用「空白 / 斜杠」切分
   * ------------------------------------------------------------------ */
  lunr.tokenizer = function (obj, metadata) {
    if (obj == null) return [];

    /* Just the Docs 会把已分词的数组再交回来，这里照 lunr 原样处理 */
    if (Array.isArray(obj)) {
      return obj.map(function (item) {
        return new lunr.Token(String(item).toLowerCase(), lunr.utils.clone(metadata));
      });
    }

    var str = String(obj).toLowerCase();
    var length = str.length;
    var tokens = [];

    function emit(text, at, spanLength) {
      if (!text) return;
      var tokenMetadata = lunr.utils.clone(metadata) || {};
      tokenMetadata.index = tokens.length;
      /* at === null 表示「只参与匹配、不参与高亮」，见 emitCjkRun 的说明 */
      if (at !== null) {
        tokenMetadata.position = [at, spanLength];
      }
      tokens.push(new lunr.Token(text, tokenMetadata));
    }

    /* 中文段：长度 1 保留原字；长度 >= 2 切成全部相邻二字组
     *
     * 为什么只有偶数起点的二字组带 position：
     * Just the Docs 的 addHighlightedText 是按「位置区间依次推进」来拼接结果的
     *   span = text.substring(index, position[0]); index = position[0] + position[1];
     * 它默认位置区间**已排序且互不重叠**。而二字组天生重叠
     *（「召回引擎」→ 召回@0、回引@1、引擎@2），重叠区间会让 index 来回倒退，
     * 把同一个字吐两次，标题会渲染成「召回回引引擎」。
     * 因此这里把二字组拆成两组：
     *   偶数起点 → 带 position（相邻偶数区间天然不重叠）→ 负责高亮
     *   奇数起点 → 不带 position → 只负责匹配，保证召回不丢
     * 两组并集仍是全部相邻二字组，召回率与逐个切分一致。
     * 又因为 lunr 的 matchData.metadata 以「词条」为键，同一个词条只出现一次，
     * 所以不会因为查询里重复出现同一个词而重复累加位置。 */
    function emitCjkRun(run, at) {
      if (run.length === 1) {
        emit(run, at, 1);
        return;
      }
      for (var i = 0; i + 2 <= run.length; i++) {
        var isAnchor = i % 2 === 0;
        emit(run.slice(i, i + 2), isAnchor ? at + i : null, isAnchor ? 2 : 0);
      }
    }

    /* 英文段：按空白/斜杠切分，丢弃分隔符但保留精确字符偏移 */
    function emitLatinRun(run, at) {
      var cursor = 0;
      while (cursor < run.length) {
        while (cursor < run.length && IS_SEPARATOR.test(run.charAt(cursor))) cursor++;
        var start = cursor;
        while (cursor < run.length && !IS_SEPARATOR.test(run.charAt(cursor))) cursor++;
        if (cursor > start) emit(run.slice(start, cursor), at + start, cursor - start);
      }
    }

    /* 扫描连续同类字符，按段 flush；i 走到 length 时用「取反」强制收尾 */
    var runStart = 0;
    var runIsCjk = length > 0 && isCjk(str.charCodeAt(0));

    for (var i = 1; i <= length; i++) {
      var nextIsCjk = i < length ? isCjk(str.charCodeAt(i)) : !runIsCjk;
      if (nextIsCjk === runIsCjk) continue;

      var run = str.slice(runStart, i);
      if (runIsCjk) emitCjkRun(run, runStart);
      else emitLatinRun(run, runStart);

      runStart = i;
      runIsCjk = nextIsCjk;
    }

    return tokens;
  };

  /* Just the Docs 会就地改写这个值，这里显式声明成站点期望的分隔符 */
  lunr.tokenizer.separator = /[\s/]+/;

  /* ------------------------------------------------------------------ *
   * 4) Query#term：显式把数组展开成多个子句
   *
   * Just the Docs 的查询写法是 `query.term(lunr.tokenizer(input), opts)`，
   * 传进来的是「词条数组」。这里逐个展开并统一转成字符串，避免整个数组
   * 被隐式拼成一个词条（两个中文二元组会拼成 "记忆,忆召" 这种不存在的词）。
   * ------------------------------------------------------------------ */
  if (lunr.Query && lunr.Query.prototype && lunr.Query.prototype.term) {
    var originalTerm = lunr.Query.prototype.term;

    lunr.Query.prototype.term = function (term, options) {
      if (Array.isArray(term)) {
        for (var i = 0; i < term.length; i++) {
          originalTerm.call(
            this,
            String(term[i]),
            options ? lunr.utils.clone(options) : options
          );
        }
        return this;
      }
      return originalTerm.call(this, term, options);
    };
  }
})();
