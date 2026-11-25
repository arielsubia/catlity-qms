# One sheet on catlity-qms-dev-compliance. The dataset grain is one row per
# audit-finding: an audit with no finding keeps a null finding_id. Audit
# visuals use a distinct count of audit_id. Finding visuals count finding_id
# and drop those null rows, so an audit without findings still counts in the
# compliance tile and the donut.
#
# Titles are English, like the rest of the configuration. Category values stay
# as stored codes (planned, major_nc, open). The Spanish mockup
# docs/diagrams/dashboard-kpis.png is didactic and is not published here.
# Open findings, findings by status, overdue corrective actions, logos, and an
# industry subtitle are on that mockup only.
#
# The date control is a parameter, not the June-November sample on the mockup.
# The wide default keeps the first view from opening empty. terraform validate
# checks this schema. It does not ask QuickSight whether the calculated
# expression is accepted. That check happens on the later apply.

resource "aws_quicksight_dashboard" "kpis" {
  dashboard_id        = "${local.name_prefix}-kpis"
  name                = "${local.name_prefix}-kpis"
  version_description = "Compliance KPI visuals"

  definition {
    data_set_identifiers_declarations {
      data_set_arn = aws_quicksight_data_set.compliance.arn
      identifier   = "compliance"
    }

    parameter_declarations {
      date_time_parameter_declaration {
        name             = "StartDate"
        time_granularity = "DAY"

        default_values {
          static_values = ["2020-01-01T00:00:00Z"]
        }
      }
    }

    parameter_declarations {
      date_time_parameter_declaration {
        name             = "EndDate"
        time_granularity = "DAY"

        default_values {
          static_values = ["2030-12-31T00:00:00Z"]
        }
      }
    }

    filter_groups {
      cross_dataset   = "SINGLE_DATASET"
      filter_group_id = "planned-date"
      status          = "ENABLED"

      filters {
        time_range_filter {
          filter_id        = "planned-date"
          null_option      = "NON_NULLS_ONLY"
          include_minimum  = true
          include_maximum  = true
          time_granularity = "DAY"

          column {
            column_name         = "planned_date"
            data_set_identifier = "compliance"
          }

          range_minimum_value {
            parameter = "StartDate"
          }

          range_maximum_value {
            parameter = "EndDate"
          }
        }
      }

      scope_configuration {
        selected_sheets {
          sheet_visual_scoping_configurations {
            scope    = "ALL_VISUALS"
            sheet_id = "kpis"
          }
        }
      }
    }

    # Audits with no finding stay in the compliance tile and the donut.
    filter_groups {
      cross_dataset   = "SINGLE_DATASET"
      filter_group_id = "findings-only"
      status          = "ENABLED"

      filters {
        category_filter {
          filter_id = "findings-only"

          column {
            column_name         = "finding_id"
            data_set_identifier = "compliance"
          }

          configuration {
            custom_filter_configuration {
              match_operator     = "EQUALS"
              null_option        = "NON_NULLS_ONLY"
              select_all_options = "FILTER_ALL_VALUES"
            }
          }
        }
      }

      scope_configuration {
        selected_sheets {
          sheet_visual_scoping_configurations {
            scope      = "SELECTED_VISUALS"
            sheet_id   = "kpis"
            visual_ids = ["findings-by-type", "monthly-trends", "top-clauses"]
          }
        }
      }
    }

    # Limited to this visual. A sheet-wide top filter would cut every chart.
    # time_granularity is required by this provider schema. clause_reference is
    # text, so the value is unused until the apply confirms QuickSight accepts it.
    filter_groups {
      cross_dataset   = "SINGLE_DATASET"
      filter_group_id = "top-clauses"
      status          = "ENABLED"

      filters {
        top_bottom_filter {
          filter_id        = "top-clauses"
          limit            = 5
          time_granularity = "DAY"

          column {
            column_name         = "clause_reference"
            data_set_identifier = "compliance"
          }

          aggregation_sort_configuration {
            sort_direction = "DESC"

            column {
              column_name         = "finding_id"
              data_set_identifier = "compliance"
            }

            aggregation_function {
              categorical_aggregation_function = "COUNT"
            }
          }
        }
      }

      filters {
        category_filter {
          filter_id = "clauses-present"

          column {
            column_name         = "clause_reference"
            data_set_identifier = "compliance"
          }

          configuration {
            custom_filter_configuration {
              match_operator     = "EQUALS"
              null_option        = "NON_NULLS_ONLY"
              select_all_options = "FILTER_ALL_VALUES"
            }
          }
        }
      }

      scope_configuration {
        selected_sheets {
          sheet_visual_scoping_configurations {
            scope      = "SELECTED_VISUALS"
            sheet_id   = "kpis"
            visual_ids = ["top-clauses"]
          }
        }
      }
    }

    sheets {
      sheet_id = "kpis"
      name     = "Compliance"
      title    = "Compliance"

      filter_controls {
        date_time_picker {
          filter_control_id = "planned-date-picker"
          source_filter_id  = "planned-date"
          title             = "Date range"
          type              = "DATE_RANGE"
        }
      }

      visuals {
        kpi_visual {
          visual_id = "compliance-pct"

          title {
            visibility = "VISIBLE"

            format_text {
              plain_text = "Compliance %"
            }
          }

          chart_configuration {
            field_wells {
              values {
                calculated_measure_field {
                  field_id   = "compliance-pct-value"
                  expression = "distinct_countIf({audit_id}, {audit_status} = 'completed' OR {audit_status} = 'closed') / distinct_count({audit_id}) * 100"
                }
              }
            }
          }
        }
      }

      visuals {
        bar_chart_visual {
          visual_id = "findings-by-type"

          title {
            visibility = "VISIBLE"

            format_text {
              plain_text = "Findings by type"
            }
          }

          chart_configuration {
            orientation      = "VERTICAL"
            bars_arrangement = "CLUSTERED"

            field_wells {
              bar_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    field_id = "finding-type"

                    column {
                      column_name         = "finding_type"
                      data_set_identifier = "compliance"
                    }
                  }
                }

                values {
                  categorical_measure_field {
                    field_id             = "finding-type-count"
                    aggregation_function = "COUNT"

                    column {
                      column_name         = "finding_id"
                      data_set_identifier = "compliance"
                    }
                  }
                }
              }
            }
          }
        }
      }

      visuals {
        line_chart_visual {
          visual_id = "monthly-trends"

          title {
            visibility = "VISIBLE"

            format_text {
              plain_text = "Monthly trends"
            }
          }

          chart_configuration {
            field_wells {
              line_chart_aggregated_field_wells {
                category {
                  date_dimension_field {
                    field_id         = "finding-month"
                    date_granularity = "MONTH"

                    column {
                      column_name         = "finding_created_at"
                      data_set_identifier = "compliance"
                    }
                  }
                }

                values {
                  categorical_measure_field {
                    field_id             = "finding-month-count"
                    aggregation_function = "COUNT"

                    column {
                      column_name         = "finding_id"
                      data_set_identifier = "compliance"
                    }
                  }
                }
              }
            }
          }
        }
      }

      visuals {
        bar_chart_visual {
          visual_id = "top-clauses"

          title {
            visibility = "VISIBLE"

            format_text {
              plain_text = "Top 5 clauses"
            }
          }

          chart_configuration {
            orientation      = "HORIZONTAL"
            bars_arrangement = "CLUSTERED"

            field_wells {
              bar_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    field_id = "clause-reference"

                    column {
                      column_name         = "clause_reference"
                      data_set_identifier = "compliance"
                    }
                  }
                }

                values {
                  categorical_measure_field {
                    field_id             = "clause-count"
                    aggregation_function = "COUNT"

                    column {
                      column_name         = "finding_id"
                      data_set_identifier = "compliance"
                    }
                  }
                }
              }
            }

            sort_configuration {
              category_sort {
                column_sort {
                  direction = "DESC"

                  sort_by {
                    column_name         = "finding_id"
                    data_set_identifier = "compliance"
                  }

                  aggregation_function {
                    categorical_aggregation_function = "COUNT"
                  }
                }
              }
            }
          }
        }
      }

      visuals {
        pie_chart_visual {
          visual_id = "audits-by-status"

          title {
            visibility = "VISIBLE"

            format_text {
              plain_text = "Audits by status"
            }
          }

          chart_configuration {
            donut_options {
              arc_options {
                arc_thickness = "MEDIUM"
              }

              donut_center_options {
                label_visibility = "VISIBLE"
              }
            }

            field_wells {
              pie_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    field_id = "audit-status"

                    column {
                      column_name         = "audit_status"
                      data_set_identifier = "compliance"
                    }
                  }
                }

                values {
                  categorical_measure_field {
                    field_id             = "audit-status-count"
                    aggregation_function = "DISTINCT_COUNT"

                    column {
                      column_name         = "audit_id"
                      data_set_identifier = "compliance"
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-kpis"
  })
}
