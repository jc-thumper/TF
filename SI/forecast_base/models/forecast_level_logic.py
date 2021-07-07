# -*- coding: utf-8 -*-
import abc


class ForecastLevelLogic(object):
    """
    Abstract class to define methods for each forecast level
    """
    __metaclass__ = abc.ABCMeta

    ####################################
    # General functions
    ####################################

    @abc.abstractmethod
    def get_full_keys(self):
        raise NotImplementedError

    @abc.abstractmethod
    def get_required_fields(self):
        raise NotImplementedError

    @abc.abstractmethod
    def get_product_keys(self, **kwargs):
        """
        :param kwargs:
        :return:
        :rtype: list[str]
        """
        raise NotImplementedError

    ####################################
    # Product Product functions
    ####################################
    @abc.abstractmethod
    def get_master_available_qty_dict(self, objs, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def compute_master_product_qty(self, objs, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def compute_qty_on_hand(self, obj, model_name, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_product_service_level_infos_by_keys(self, obj, model_name, tuple_keys, tuple_values, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_total_demand_inventory(self, obj, model_name, product_ids, current_date, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_total_supply_inventory(self, obj, model_name, product_ids, current_date, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_daily_forecasting_value(self, obj, model_name, line_ids, period_type='daily', **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_sold_qty_of_products(self, obj, model_name, period_type='MONTH', period_number=-12, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_conflict_fields_for_rrwf_tracker(self, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def create_product_info_df_to_compute_under_overstock(self, obj, model_name, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_demand_of_products(self, obj, model_name, period_type='MONTH', period_number=-6, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_procurement_cycle_of_products(self, obj, model_name, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_min_max_order_qty(self, obj, model_name, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_total_si_forecast_of_products(self, obj, model_name, product_ids=None, current_time=None, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_conflict_fields_for_uo_stock_tracker(self, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def create_initial_records_for_rrwf(self, obj, model, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_product_infos_for_rrwf(self, record, **kwargs):
        """ Function return the product information for reordering rule with forecast record
        :param record: ReorderingRulesWithForecast
        :param kwargs:
        :return:
        :rtype: dict
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_products_info_dict(self, obj, product_ids, **kwargs):
        """ Function return the product information for reordering rule with forecast record
        :param obj:
        :param product_ids: list[int]
        :param kwargs:
        :return:
        Ex: {
                product_id: {
                    'product_id':...,
                    'master_product_id':...
                }
            }
        :rtype: dict
        """
        raise NotImplementedError

    @abc.abstractmethod
    def set_total_si_forecast_of_products(self, obj, model, period_type='procurement_cycle', **kwargs):
        raise NotImplementedError

    ####################################
    # Demand Classification Result API
    ####################################

    @abc.abstractmethod
    def get_conflict_fields_for_demand_classification_result(self, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_latest_records_dict_for_demand_classification_result(self, obj, model, created_date, **kwargs):
        raise NotImplementedError

    ####################################
    # Service Level Result API
    ####################################

    @abc.abstractmethod
    def get_conflict_fields_for_service_level_result(self, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_latest_records_dict_for_service_level_result(self, obj, model, created_date, **kwargs):
        raise NotImplementedError

    ####################################
    # Product Classification Info
    ####################################

    @abc.abstractmethod
    def update_product_clsf_info_from_demand_classification_result(self, obj, model, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def update_product_clsf_info_from_service_level_result(self, obj, model, **kwargs):
        raise NotImplementedError

    ####################################
    # Summarize Result API
    ####################################

    @abc.abstractmethod
    def get_conflict_fields_for_summarize_rec_result(self, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_latest_records_dict_for_summarize_rec_result(self, obj, model, created_date, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def update_records_for_summarize_data_line(self, obj, list_data, **kwargs):
        raise NotImplementedError

    ####################################
    # Forecast Result API
    ####################################

    @abc.abstractmethod
    def get_conflict_fields_for_forecast_result(self, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def update_records_for_forecast_result_adjust_line(self, obj, model, created_date, pub_time, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def create_or_update_records_in_forecast_result_daily(self, obj, model_name, line_ids, **kwargs):
        raise NotImplementedError

    ####################################
    # Understock Overstock Report API
    ####################################

    @abc.abstractmethod
    def update_latest_records_for_uo_stock(self, obj, model, created_date, **kwargs):
        raise NotImplementedError

    ####################################
    # Investment Report
    ####################################

    @abc.abstractmethod
    def get_forecast_demand_values_for_investment_report(self, obj, model, product_ids, warehouse_ids, company_id,
                                                         from_start_date, to_start_date, invest_type, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_grouped_key_for_investment_report(self):
        raise NotImplementedError

    ####################################
    # Product Age Report API
    ####################################

    @abc.abstractmethod
    def get_conflict_fields_for_product_age_tracker(self, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_stock_on_hand_for_product_age_report(self, obj, model, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def update_latest_records_for_product_age(self, obj, model, created_date, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_po_lines_in_range_for_product_age_report(self, obj, model, company_id, product_ids, start_date=None,
                                                     end_date=None,
                                                     **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_on_order_values_for_heavy_stock_items(self, obj, model, company_id, product_ids, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_mo_lines_in_range_for_product_age_report(self, obj, model, company_id, product_ids, start_date=None,
                                                     end_date=None, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_inventory_adjustment_lines_for_product_age_report(self, obj, model, company_id, product_ids, **kwargs):
        raise NotImplementedError
