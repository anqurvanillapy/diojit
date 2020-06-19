// Generated by BUCKLESCRIPT, PLEASE EDIT WITH CARE
'use strict';

var $$Array = require("bs-platform/lib/js/array.js");
var Caml_array = require("bs-platform/lib/js/caml_array.js");
var Caml_exceptions = require("bs-platform/lib/js/caml_exceptions.js");

var IndexExceeded = Caml_exceptions.create("Darray-Jit.IndexExceeded");

var GrowShorter = Caml_exceptions.create("Darray-Jit.GrowShorter");

var AccessingEmptyList = Caml_exceptions.create("Darray-Jit.AccessingEmptyList");

function exp(n) {
  return 1 + (n << 2) | 0;
}

function from_array(xs) {
  return {
          data: xs,
          len: xs.length
        };
}

function to_list(param) {
  return $$Array.to_list(param.data);
}

function make(n, elt) {
  return {
          data: Caml_array.caml_make_vect(n, elt),
          len: n
        };
}

function len(param) {
  return param.len;
}

function empty(param) {
  return {
          data: Caml_array.caml_make_vect(0, 0),
          len: 0
        };
}

function update(i, elt, darray) {
  if (i < darray.len) {
    darray.data[i] = elt;
    return ;
  }
  throw [
        IndexExceeded,
        i
      ];
}

function get(i, darray) {
  if (i < darray.len) {
    return Caml_array.caml_array_get(darray.data, i);
  }
  throw [
        IndexExceeded,
        i
      ];
}

function grow(darray, n) {
  if (darray.len > n) {
    throw GrowShorter;
  }
  var data = Caml_array.caml_make_vect(exp(n), 0);
  for(var ith = 0; ith < n; ++ith){
    data[ith] = darray.data[ith];
  }
  darray.data = data;
  
}

function append(darray, elt) {
  var len = darray.len;
  if (len >= darray.data.length) {
    grow(darray, len);
  }
  darray.len = len + 1 | 0;
  darray.data[len] = elt;
  
}

function pop(darray) {
  if (darray.len <= 1) {
    throw AccessingEmptyList;
  }
  darray.len = darray.len - 1 | 0;
  
}

exports.IndexExceeded = IndexExceeded;
exports.GrowShorter = GrowShorter;
exports.AccessingEmptyList = AccessingEmptyList;
exports.exp = exp;
exports.from_array = from_array;
exports.to_list = to_list;
exports.make = make;
exports.len = len;
exports.empty = empty;
exports.update = update;
exports.get = get;
exports.grow = grow;
exports.append = append;
exports.pop = pop;
/* No side effect */
