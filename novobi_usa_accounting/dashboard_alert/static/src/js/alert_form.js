odoo.define('dashboard_alert.AlertForm', function (require) {
    "use strict";

    var Widget = require('web.Widget');
    var MessageDialog = require('dashboard_alert.MessageDialog');
    var core = require('web.core');

    var _t = core._t;

    var AlertForm = Widget.extend({
        events:{
            'click #btn_submit': 'onSubmit',
        },

        init: function () {
            this._super.apply(this, arguments);
            console.log("test");
        },

        onSubmit: function(ev){
            var self = this;
            var ajax = require('web.ajax');
            var status = this.$el.find('#txt_status')[0].value;
            var token = this.$el.find('#txt_token')[0].value;
            ajax.jsonRpc('/web/dashboard_alert/change_subscribe_status', 'call', {
                token: token,
                status: status
            }).then(function (result) {
                if (result.error == undefined) {
                    // alert(result.mess);
                    self.$el.find('#btn_submit').addClass('o_hidden');
                    self.$el.find('.txt_mess')[0].textContent = _t(result.mess);

                    return mess("Unsubscribe", _t(result.mess), function () {
                        var url = "../../";
                        location.replace(url);
                    })

                } else {
                    self.$el.find('#btn_submit').addClass('o_hidden');
                    self.$el.find('.txt_mess').addClass('alert-danger');
                    self.$el.find('.txt_mess').removeClass('alert-success');
                    self.$el.find('.txt_mess')[0].textContent = _t(result.error);
                }
            });
        },
    });

    var SnoozeForm = Widget.extend({
        events:{
            'click #btn_snooze': 'onSnooze',
            'click #btn_cancel': 'onDismiss',
        },

        onSnooze: function (ev) {
            var self = this;
            var ajax = require('web.ajax');
            var token = this.$el.find('#txt_token')[0].value;
            var minutes_sent = this.$el.find('#slt_time_snooze')[0].value;
            ajax.jsonRpc('/web/dashboard_alert/update_time_sent_again', 'call', {
                token: token,
                minutes_sent: minutes_sent
            }).then(function (result) {

                if (result.mess !== undefined){
                    var time_rec_new_alert = new Date(result.time_receive);
                    var time_formated = strftime('%A %b %e %Y %l:%M %P', time_rec_new_alert);

                    self.$el.find('.txt_mess')[0].innerHTML = result.mess + time_formated;
                    self.$el.find('.txt_mess').removeClass('alert-danger alert');
                    self.$el.find('.txt_mess').addClass('alert-success alert');

                    self.$el.find('#select_option').addClass('o_hidden');
                    self.$el.find('#btn_snooze').addClass('o_hidden');
                    self.$el.find('#btn_cancel').addClass('o_hidden');
                } else {
                    self.$el.find('.txt_mess')[0].innerHTML = result.error;
                    self.$el.find('.txt_mess').removeClass('alert-success alert');
                    self.$el.find('.txt_mess').addClass('alert-danger alert');
                }

            })
        },

        onDismiss: function (ev) {
            var url = "../../";
            location.replace(url);
        },
    });

    var MoreSettingsForm = Widget.extend({
        events:{
            'click #btn_update': 'onUpdate',
        },

        onUpdate: function (ev) {
            var self = this;
            var token = this.$el.find('#txt_token')[0].value;

            var subject = this.$el.find('#txt_subject')[0].value;
            var condition = this.$el.find('#slt_condition')[0].value;
            var threshold = this.$el.find('#txt_threshold')[0].value;
            var time_alert = this.$el.find('#slt_time_alert')[0].value;

            self.update_setting(token, subject, condition, threshold, time_alert);
        },

        update_setting: function (token, subject, condition, threshold, time_alert, direct_update=false) {
            var self = this;
            var ajax = require('web.ajax');
            ajax.jsonRpc('/web/dashboard_alert/update_setting', 'call', {
                token: token,
                subject: subject,
                condition: condition,
                threshold: threshold,
                time_alert: time_alert,
                direct_update: direct_update
            }).then(function (result) {
                self.$el.find('#txt_token')[0].value = result.token;
                if (result.error == undefined) {
                    if (result.re_update) {
                        return mess('More Setting', result.mess, function () {
                            self.update_setting(token, subject, condition, threshold, time_alert, true);
                        }, true);
                    } else {
                        self.$el.find('#setting_content').addClass('o_hidden');
                        self.$el.find('#btn_update').addClass('o_hidden');
                        return mess('More Setting', result.mess, function () {
                            var url = "../../";
                            location.replace(url);
                        });
                    }
                } else {
                    return mess('More Setting', result.error, function () {});
                }
            })
        },
    });

    function mess(title, mess, action_ok, confirm_option=false) {
        return new MessageDialog.MessageDialog(self, {
            size: 'medium',
            $content: $('<div>', {
                html: _t(mess)
            }),
            confirm: confirm_option,
            title: _t(title),
            action_ok: action_ok
        }).open()
    };

    function strftime(sFormat, date) {
        if (!(date instanceof Date)) date = new Date();
        var nDay = date.getDay(),
            nDate = date.getDate(),
            nMonth = date.getMonth(),
            nYear = date.getFullYear(),
            nHour = date.getHours(),
            aDays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
            aMonths = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
            aDayCount = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334],
            isLeapYear = function() {
                if ((nYear&3)!==0) return false;
                return nYear%100!==0 || nYear%400===0;
            },
            getThursday = function() {
                var target = new Date(date);
                target.setDate(nDate - ((nDay+6)%7) + 3);
                return target;
            },
            zeroPad = function(nNum, nPad) {
                return ('' + (Math.pow(10, nPad) + nNum)).slice(1);
            };
        return sFormat.replace(/%[a-z]/gi, function(sMatch) {
            return {
                '%a': aDays[nDay].slice(0,3),
                '%A': aDays[nDay],
                '%b': aMonths[nMonth].slice(0,3),
                '%B': aMonths[nMonth],
                '%c': date.toUTCString(),
                '%C': Math.floor(nYear/100),
                '%d': zeroPad(nDate, 2),
                '%e': nDate,
                '%F': date.toISOString().slice(0,10),
                '%G': getThursday().getFullYear(),
                '%g': ('' + getThursday().getFullYear()).slice(2),
                '%H': zeroPad(nHour, 2),
                '%I': zeroPad((nHour+11)%12 + 1, 2),
                '%j': zeroPad(aDayCount[nMonth] + nDate + ((nMonth>1 && isLeapYear()) ? 1 : 0), 3),
                '%k': '' + nHour,
                '%l': (nHour+11)%12 + 1,
                '%m': zeroPad(nMonth + 1, 2),
                '%M': zeroPad(date.getMinutes(), 2),
                '%P': (nHour<12) ? 'AM' : 'PM',
                '%p': (nHour<12) ? 'am' : 'pm',
                '%s': Math.round(date.getTime()/1000),
                '%S': zeroPad(date.getSeconds(), 2),
                '%u': nDay || 7,
                '%V': (function() {
                    var target = getThursday(),
                        n1stThu = target.valueOf();
                    target.setMonth(0, 1);
                    var nJan1 = target.getDay();
                    if (nJan1!==4) target.setMonth(0, 1 + ((4-nJan1)+7)%7);
                    return zeroPad(1 + Math.ceil((n1stThu-target)/604800000), 2);
                })(),
                '%w': '' + nDay,
                '%x': date.toLocaleDateString(),
                '%X': date.toLocaleTimeString(),
                '%y': ('' + nYear).slice(2),
                '%Y': nYear,
                '%z': date.toTimeString().replace(/.+GMT([+-]\d+).+/, '$1'),
                '%Z': date.toTimeString().replace(/.+\((.+?)\)$/, '$1')
            }[sMatch] || sMatch;
        });
    };

    require('web.dom_ready');

    var AlertFormWidget = new AlertForm();
    var SnoozeFormWidget = new SnoozeForm();
    var MoreSettingsWidget = new MoreSettingsForm();
    AlertFormWidget.attachTo($("#unsubscribe_alert_form_section"));
    SnoozeFormWidget.attachTo($("#snooze_alert_form_section"));
    MoreSettingsWidget.attachTo($("#alert_more_settings_form_section"));
});
