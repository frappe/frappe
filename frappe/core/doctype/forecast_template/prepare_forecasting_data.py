import frappe
from frappe.utils import (flt, nowdate, add_years, getdate, formatdate)

class ExponentialSmoothingForecast(object):
	def forecast_future_data(self):
		self.alpha = flt(self.alpha)
		self.beta = flt(self.beta)
		self.gamma = flt(self.gamma)

		if self.forecasting_method == "Single Exponential Smoothing":
			self.get_data_using_single_exponential_smoothing()
		elif self.forecasting_method == "Double Exponential Smoothing":
			self.get_data_using_double_exponential_smoothing()
		else:
			self.get_data_using_triple_exponential_smoothing()

	def get_data_using_single_exponential_smoothing(self):
		for key, value in self.period_wise_data.items():
			forecast_data = []
			for period in self.period_list:
				forecast_key = "forecast_" + period.key

				if value.get(period.key) and not forecast_data:
					value[forecast_key] = flt(value.get("avg", 0)) or flt(value.get(period.key))

				elif forecast_data:
					previous_period_data = forecast_data[-1]
					value[forecast_key] = (previous_period_data[1] +
						flt(self.alpha) * (
							flt(previous_period_data[0]) - flt(previous_period_data[1])
						)
					)

				if value.get(forecast_key):
					# will be use to forecaset next period
					forecast_data.append([value.get(period.key), value.get(forecast_key)])

	def get_data_using_triple_exponential_smoothing(self):
		period_start_date = self.period_list[0].current_period_start_date
		period_end_date = self.period_list[0].current_period_end_date

		for key, value in self.period_wise_data.items():
			self.index = 0
			forecast_data = []
			for period in self.period_list:
				self.level_key, self.trend_key, self.seasonal_key, self.forecast_key = ["level_" + period.key,
					"trend_" + period.key, "seasonal_" + period.key, "forecast_" + period.key]

				value[self.forecast_key] = 0.0
				if (period.current_period_start_date == period_start_date and
					period.current_period_end_date == period_end_date) or not forecast_data:
					value[self.seasonal_key] = flt(value.get(period.key) / value.get("avg")
						if value.get(period.key) and value.get("avg") else 0.0)
				else:
					self.get_level_trend_for_seasonal(value, period, forecast_data)

					value[self.seasonal_key] = flt(flt(self.gamma) *
						( (value.get(period.key) / value.get(self.level_key))
							if value.get(self.level_key) else 0.0 ) +
						(1.0 - flt(self.gamma)) * value.get("seasonal_" + period.last_period_key, 0.0)
					)

					self.get_forecast_for_seasonal(value, period, forecast_data)

				if (self.from_date > period.from_date or value.get(period.key)) and value.get(self.seasonal_key):
					forecast_data.append([value.get(self.level_key, 0), value.get(self.trend_key, 0),
						value.get(self.seasonal_key, 0), value.get(self.forecast_key, 0), value.get(period.key)])

	def get_level_trend_for_seasonal(self, value, period, forecast_data):
		last_period_data = forecast_data[-1]
		if self.index == 0:
			value[self.level_key] = (value.get(period.key) / value.get("seasonal_" + period.last_period_key)
				if value.get(period.key) else 0.0)
			value[self.trend_key] = value["level_" + period.key] - ((value.get(period.key) / last_period_data[2])
				if last_period_data[2] else 0)
			self.index = 1
		else:
			value[self.level_key] = (self.alpha *
				( (value.get(period.key) / value.get("seasonal_" + period.last_period_key))
					if value.get("seasonal_" + period.last_period_key) else 0.0 ) +
				(1.0 - self.alpha) * (last_period_data[0] + last_period_data[1])
			)

			value[self.trend_key] = (self.beta *
				flt(value[self.level_key] - last_period_data[0]) +
				(1.0 - self.beta) * value.get("seasonal_" + period.last_period_key, 0.0) * last_period_data[1]
			)

	def get_forecast_for_seasonal(self, value, period, forecast_data):
		if self.index > 0:
			last_period_data = forecast_data[-1]

			value[self.forecast_key] = flt((last_period_data[0] + (last_period_data[1] * self.index)) *
				value.get("seasonal_" + period.last_period_key, 0.0))

			if not (self.from_date > period.from_date or value.get(period.key)):
				self.index += 1

	def get_data_using_double_exponential_smoothing(self):
		for key, value in self.period_wise_data.items():
			forecast_data = []
			self.index = 0
			for period in self.period_list:
				self.level_key, self.trend_key, self.forecast_key = ["level_" + period.key,
					"trend_" + period.key, "forecast_" + period.key]

				if forecast_data:
					self.get_level_trend_for_double_exponential(value, period, forecast_data)
					self.get_forecast_for_level_and_trend(value, period, forecast_data)

				if value.get(period.key) or value.get(self.level_key):
					self.index = 1
					forecast_data.append([value.get(self.level_key, 0), value.get(self.trend_key, 0),
						value.get(self.forecast_key, 0), value.get(period.key)])

	def get_level_trend_for_double_exponential(self, value, period, forecast_data):
		last_period_data = forecast_data[-1]
		if not (last_period_data[0] and last_period_data[1]) and last_period_data[3]:
			value[self.level_key] = flt(value.get(period.key, 0))
			value[self.trend_key] = flt(value.get(period.key, 0) - flt(last_period_data[3]))
		else:
			value[self.level_key] = flt( (self.alpha) * value.get(period.key, 0) + (1 - flt(self.alpha))
				* (last_period_data[0] + last_period_data[1]) )
			value[self.trend_key] = flt( (self.beta) * (value.get(period.key, 0) - flt(last_period_data[3]))
				+ (1 - flt(self.beta)) * (last_period_data[1]) )

	def get_forecast_for_level_and_trend(self, value, period, forecast_data):
		if self.index > 0:
			last_period_data = forecast_data[-1]
			value[self.forecast_key] = flt(last_period_data[0]) + (flt(last_period_data[1]) * self.index)

			if not (self.from_date > period.from_date or value.get(self.level_key)):
				self.index += 1