// Generated by BUCKLESCRIPT, PLEASE EDIT WITH CARE
'use strict';

var List = require("bs-platform/lib/js/list.js");
var Curry = require("bs-platform/lib/js/curry.js");
var Caml_obj = require("bs-platform/lib/js/caml_obj.js");
var Caml_option = require("bs-platform/lib/js/caml_option.js");

function find_opt(key, _param) {
  while(true) {
    var param = _param;
    if (!param) {
      return ;
    }
    var match = param[0];
    if (Caml_obj.caml_equal(match[0], key)) {
      return Caml_option.some(match[1]);
    }
    _param = param[1];
    continue ;
  };
}

function find_default(a, key, map) {
  var a$1 = find_opt(key, map);
  if (a$1 !== undefined) {
    return Caml_option.valFromOption(a$1);
  } else {
    return a;
  }
}

function add(k, v, xs) {
  return /* :: */[
          /* tuple */[
            k,
            v
          ],
          xs
        ];
}

function diffkeys(xs1, xs2) {
  var pred = function (param) {
    return !List.mem_assoc(param[0], xs2);
  };
  return List.filter(pred)(xs1);
}

function intersect(f, xs1, xs2) {
  return List.fold_right((function (param, b) {
                var ak = param[0];
                var v$prime = find_opt(ak, xs2);
                if (v$prime !== undefined) {
                  return /* :: */[
                          /* tuple */[
                            ak,
                            Curry._2(f, param[1], Caml_option.valFromOption(v$prime))
                          ],
                          b
                        ];
                } else {
                  return b;
                }
              }), xs1, /* [] */0);
}

function is_empty(xs) {
  return xs === /* [] */0;
}

function map(f, param) {
  if (!param) {
    return /* [] */0;
  }
  var match = param[0];
  return /* :: */[
          /* tuple */[
            match[0],
            Curry._1(f, match[1])
          ],
          map(f, param[1])
        ];
}

var find = List.assoc;

var mem = List.mem_assoc;

var remove = List.remove_assoc;

var empty = /* [] */0;

var len = List.length;

exports.find = find;
exports.find_opt = find_opt;
exports.find_default = find_default;
exports.mem = mem;
exports.remove = remove;
exports.add = add;
exports.empty = empty;
exports.diffkeys = diffkeys;
exports.intersect = intersect;
exports.is_empty = is_empty;
exports.len = len;
exports.map = map;
/* No side effect */
