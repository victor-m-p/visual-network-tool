/*
Copyright (C) 2024 Max R. P. Grossmann

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program; if not, write to the Free Software Foundation,
Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
*/

console.assert(typeof mgsliders === "undefined", "mgslider.js may not be loaded multiple times");

var mgsliders = Array();

mgsliders.lookup = function (which) {
    for (var j = 0; j < mgsliders.length; j++) {
        if (mgsliders[j].field == which) {
            return mgsliders[j].obj;
        }
    }

    return undefined;
};

function mgslider(field, min, max, step) {
    this.field = field;
    this.min = parseFloat(min);
    this.max = parseFloat(max);
    this.step = parseFloat(step);
    this.direction = 1;
    this.digits = this.suggest_digits(step);
    this.hook = function (slider, value) { };
    this.recall = false;

    this.prefix = "mgslider_yF5sTZLy";
    this.yourvalue = "Your value";

    mgsliders.push({ field: field, obj: this });
}

mgslider.prototype.fzero = function (s) {
    for (var c = s.length - 1; c >= 0; c--) {
        if (s[c] != "0") {
            return c;
        }
    }

    return 0;
};

mgslider.prototype.suggest_digits = function (x) {
    x = x.toFixed(10);
    return this.fzero(x) - x.search(/\./);
};

mgslider.prototype.f2s = function (val, detect, digits) {
    if (digits) {
        return val.toFixed(digits).replace("-", "&ndash;");
    }
    else if (detect) {
        return val.toFixed(this.suggest_digits(val)).replace("-", "&ndash;");
    }
    else {
        return val.toFixed(this.digits).replace("-", "&ndash;");
    }
};

mgslider.prototype.id = function (id_) {
    if (id_ === undefined) {
        id_ = "";
    }

    return this.prefix + "_" + this.field + "_" + id_;
};

mgslider.prototype.left = function () {
    if (this.direction == 1) {
        return this.min;
    }
    else {
        return this.max;
    }
};

mgslider.prototype.right = function () {
    if (this.direction == 1) {
        return this.max;
    }
    else {
        return this.min;
    }
};

mgslider.prototype.to_internal = function (x) {
    if (this.direction == 1) {
        return 10000 + (x - this.min) / this.step;
    }
    else {
        return 10000 + (this.max - x) / this.step;
    }
};

mgslider.prototype.from_internal = function (y) {
    if (this.direction == 1) {
        return this.min - (10000 - y) * this.step;
    }
    else {
        return this.max + (10000 - y) * this.step;
    }
};

mgslider.prototype.feedback = function (value) {
    return this.yourvalue + ": <b class='mgslider-value'>" + this.f2s(value, false) + "</b>";
};

mgslider.prototype.markup = function (position) {
    var position_internal = (position === undefined) ? 10000 : this.to_internal(position);

    return "\
        <table id='" + this.id("wrapper") + "' class='mgslider-wrapper' border='0'>\
            <tr>\
                <td class='mgslider-limit'>" + this.f2s(this.left(), true) + "</td>\
                <td width='90%'>\
                    <div id='" + this.id("before") + "' class='mgslider-before' onclick='mgsliders.lookup(\"" + this.field + "\").reveal(event)'></div>\
                    <input type='range' id='" + this.id() + "' min='10000' max='" + Math.round(this.to_internal(this.right())) + "' step='1' value='" + position_internal + "' class='mgslider form-range' oninput='mgsliders.lookup(\"" + this.field + "\").change_from_slider(this)' onchange='mgsliders.lookup(\"" + this.field + "\").change_from_slider(this)'>\
                </td>\
                <td class='mgslider-limit'>" + this.f2s(this.right(), true) + "</td>\
            </tr>\
            <tr class='mgslider-feedback'>\
                <td id='" + this.id("show") + "' class='mgslider-show' colspan='3'>" + this.feedback(0) + "</td>\
            </tr>\
        </table>\
        <input type='hidden' id='" + this.id("input") + "' name='" + this.field + "' value='' />";
};

mgslider.prototype.hide = function () {
    document.getElementById(this.id()).style.display = "none";
    document.getElementById(this.id("show")).style.visibility = "hidden";
    document.getElementById(this.id("before")).style.display = "block";
};

mgslider.prototype.value = function () {
    return parseFloat(document.getElementById(this.id("input")).value);
};

mgslider.prototype.change = function () {
    var value = this.value();

    document.getElementById(this.id("show")).innerHTML = this.feedback(value);

    if (this.recall) {
        sessionStorage.setItem("mgslider__" + this.field, value);
    }

    console.assert(value >= this.min, "value must be at least slider.min");
    console.assert(value <= this.max, "value must be at most slider.max");
    console.assert(Math.abs(value % this.step) <= 0.00001, "value must be a multiple of slider.step");

    return this.hook(this, value);
};

mgslider.prototype.change_from_slider = function (slider) {
    document.getElementById(this.id("input")).value = this.from_internal(slider.value);

    this.change();
};

mgslider.prototype.reveal = function (event) {
    var now_internal = 10000 + Math.random() * (this.to_internal(this.max) - 10000); // default is legacy fallback

    if (event !== undefined && typeof event.offsetX !== undefined) {
        var max = parseInt(getComputedStyle(document.getElementById(this.id("before"))).width);
        var cur = event.offsetX;

        now_internal = 10000 + (cur / max) * (this.to_internal(this.right()) - 10000);
    }

    now_internal = Math.round(now_internal);

    this.set(this.from_internal(now_internal));
};

mgslider.prototype.set = function (new_value) {
    document.getElementById(this.id()).style.display = "block";
    document.getElementById(this.id("before")).style.display = "none";
    document.getElementById(this.id("show")).style.visibility = "visible";

    document.getElementById(this.id("input")).value = new_value;
    document.getElementById(this.id()).value = this.to_internal(new_value);

    return this.change();
};

mgslider.prototype.previous = function () {
    if ((x = sessionStorage.getItem("mgslider__" + this.field)) !== null) {
        return parseFloat(x);
    }
};

mgslider.prototype.print = function (el) {
    if (this.recall && (x = this.previous()) !== undefined) {
        el.innerHTML += this.markup(x);
        this.set(x);
    }
    else {
        el.innerHTML += this.markup();

        this.hide();
    }
};





