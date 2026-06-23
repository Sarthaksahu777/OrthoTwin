# Public GitHub Repository Tree

Excludes `archive/internal/`.

```text
OrthoTwin/
|-- .github/
|   |-- ISSUE_TEMPLATE/
|   |   |-- bug_report.md
|   |   `-- research_question.md
|   |-- workflows/
|   |   `-- ci.yml
|   `-- PULL_REQUEST_TEMPLATE.md
|-- archive/
|-- config/
|   `-- default_config.json
|-- data/
|   |-- cleaned/
|   |-- processed/
|   `-- raw/
|       |-- 1.bmp
|       |-- train.csv
|       `-- train_series_descriptions.csv
|-- docs/
|   |-- 1-s2.0-S1361841521002127-main.pdf
|   |-- 1-s2.0-S1878875025005923-main.pdf
|   |-- 1471-2474-15-152.pdf
|   |-- 2026-06-13.md
|   |-- 2105.14711v4.pdf
|   |-- 2210.14597v1.pdf
|   |-- 2306.12217v3.pdf
|   |-- 238698.pdf
|   |-- 41597_2024_Article_3090.pdf
|   |-- demo_walkthrough.md
|   |-- FUTURE_EXTENSIONS.md
|   |-- jcm-15-04127.pdf
|   |-- Knee surg  sports traumatol  arthrosc - 2025 - Diniz - Digital twin systems for musculoskeletal applications  A current.pdf
|   |-- Mertimo2022_Article_AssociationOfLumbarDiscDegener.pdf
|   |-- orthotwin_architecture.md
|   |-- orthotwin_roadmap.md
|   |-- orthotwin_v1_whitepaper.md
|   |-- qims-15-04-2944.pdf
|   |-- README.md
|   |-- s41592-020-01008-z.pdf
|   |-- s41597-024-03351-8.pdf
|   |-- scientific_limitations.md
|   |-- system_architecture.md
|   |-- the-rsna-lumbar-degenerative-imaging-spine-classification-(lumbardisc)-dataset.pdf
|   |-- the_association_of_lumbosacral_transitional.12.pdf
|   |-- Two_trajectories_of_lumbar_disc_degeneration_from_.pdf
|   `-- Welcome.md
|-- manifests/
|   |-- dataflow.json
|   |-- final_repository_manifest.json
|   |-- master_index.json
|   |-- orthotwin_v1_release_manifest.json
|   |-- orthtwin2_arrangement_log.json
|   |-- phase45_manifest.json
|   |-- phase4_manifest.json
|   |-- phase5_manifest.json
|   |-- phase6_manifest.json
|   |-- phase7_manifest.json
|   |-- phase8_manifest.json
|   |-- pipeline_validation.json
|   |-- project_graph.json
|   |-- project_inventory.json
|   |-- project_inventory_initial.json
|   |-- refactor_summary.json
|   |-- stage2_manifest.json
|   |-- stage3_manifest.json
|   `-- state_validation_report.json
|-- measurements/
|   |-- alignment/
|   |   |-- load_path_model.json
|   |   |-- local_alignment_metrics.json
|   |   `-- spine_coordinate_system.json
|   |-- calibration/
|   |   |-- imaging_metadata_report.json
|   |   |-- physical_calibration.json
|   |   `-- spacing_validation_report.json
|   |-- discs/
|   |   |-- patient_alpha_disc_ranking.json
|   |   `-- relative_disc_metrics.json
|   |-- geometry/
|   |   |-- final_project_status.json
|   |   |-- GLOBAL_reconstructed_structures(1).pkl
|   |   |-- GLOBAL_reconstructed_structures.pkl
|   |   |-- GLOBAL_reconstructed_structures_path.pkl
|   |   |-- patient_alpha_clean_measurements.json
|   |   |-- patient_alpha_component_analysis.json
|   |   |-- patient_alpha_findings.json
|   |   |-- patient_alpha_measurements.json
|   |   |-- patient_alpha_mesh_statistics.json
|   |   |-- patient_alpha_mesh_statistics_orthtwin2.json
|   |   |-- patient_alpha_pca_measurements.json
|   |   |-- patient_alpha_voxel_component_analysis.json
|   |   |-- reconstructed_structures.pkl
|   |   `-- reconstructed_structures_orthtwin2.pkl
|   |-- radiology/
|   |   |-- canal_measurements.json
|   |   |-- curvature_measurements.json
|   |   |-- disc_area_measurements.json
|   |   |-- disc_degeneration_features.json
|   |   |-- foraminal_measurements.json
|   |   |-- radiology_disc_heights.json
|   |   `-- vertebral_slippage.json
|   `-- vertebrae/
|       `-- relative_vertebral_metrics.json
|-- models/
|   |-- checkpoints/
|   |   |-- FINAL_SEGRESNET_WEIGHTED.pth
|   |   |-- segresnet_weighted_epoch12.pth
|   |   `-- showcase_patient.pt
|   `-- configs/
|-- presentation/
|   |-- ppt_assets/
|   |   |-- 01_problem/
|   |   |-- 02_segmentation/
|   |   |-- 03_reconstruction/
|   |   |-- 04_measurements/
|   |   |-- 05_state/
|   |   |-- 06_graph/
|   |   |-- 07_surgery/
|   |   |-- 08_mesh/
|   |   |-- 09_results/
|   |   |-- 10_limitations/
|   |   `-- 11_future/
|   |-- demo_script.md
|   |-- orthotwin_showcase_report.md
|   |-- ppt_storyboard.md
|   |-- presentation_dataset.json
|   `-- showcase_manifest.json
|-- reports/
|   |-- calibration/
|   |   |-- image_metadata_inventory.json
|   |   |-- patient_alpha_linkage_graph.json
|   |   |-- phase95_calibration_audit.txt
|   |   |-- phase95_manifest.json
|   |   |-- physical_calibration_decision.json
|   |   |-- reconstruction_traceback.json
|   |   `-- spacing_candidate_ranking.json
|   |-- master_audit/
|   |   |-- orthotwin_master_audit_assets/
|   |   |-- orthotwin_master_audit.md
|   |   |-- orthotwin_master_audit.pdf
|   |   `-- orthotwin_master_audit_manifest.json
|   |-- phase1/
|   |   `-- weighted_dice_results.json
|   |-- phase2/
|   |   `-- stage2_readiness_report.txt
|   |-- phase3/
|   |   |-- digital_twin_report.txt
|   |   |-- intervention_comparison.json
|   |   |-- patient_alpha_report.txt
|   |   |-- report_generator.py
|   |   |-- runtime_recovery_report.txt
|   |   |-- session_restore_report(1).txt
|   |   |-- session_restore_report.txt
|   |   |-- stage3_biomechanics_report.txt
|   |   `-- state_change_report.txt
|   |-- phase4/
|   |   |-- measurement_validation_report.txt
|   |   `-- phase4_radiology_measurements_report.txt
|   |-- phase4_5/
|   |   `-- missing_spacing_report.txt
|   |-- phase5/
|   |   |-- dashboard_state.json
|   |   |-- phase5_scenario_report.txt
|   |   |-- phase5_validation_report.json
|   |   |-- scenario_comparison_matrix.json
|   |   `-- scenario_ranking.json
|   |-- phase6/
|   |   |-- evidence/
|   |   |-- confidence_scoring.json
|   |   |-- failure_modes.json
|   |   |-- master_dashboard.json
|   |   |-- orthotwin_research_summary.md
|   |   |-- orthotwin_system_assessment.json
|   |   `-- repository_knowledge_graph.json
|   |-- phase7/
|   |   |-- geometry_vs_rule_based_breakdown.json
|   |   |-- phase7_forensic_validation_report.txt
|   |   |-- phase7_geometry_aware_surgery_report.txt
|   |   |-- phase7_limitations.json
|   |   |-- phase7_validation_report.json
|   |   |-- surgical_comparison_matrix.json
|   |   `-- surgical_dashboard.json
|   |-- phase8/
|   |   |-- mesh_impact_analysis.json
|   |   |-- orthotwin_final_prototype_report.txt
|   |   |-- phase8_limitations.json
|   |   `-- phase8_validation_report.json
|   |-- phase9/
|   |   |-- assumption_reduction_plan.json
|   |   |-- biomechanics_readiness_report.json
|   |   |-- measurement_evidence_matrix.json
|   |   |-- orthotwin_final_gap_analysis.txt
|   |   |-- orthotwin_prototype_status.json
|   |   |-- patient_alpha_spacing_audit.json
|   |   |-- phase9_manifest.json
|   |   |-- surgery_evidence_matrix.json
|   |   `-- validation_roadmap.json
|   |-- release_v1/
|   |   |-- architecture_graph.json
|   |   |-- capability_matrix.json
|   |   |-- capability_matrix_report.txt
|   |   |-- orthotwin_v1_classification.json
|   |   |-- orthotwin_v1_repository_audit.json
|   |   |-- orthotwin_v1_validation.json
|   |   |-- repository_health_report.txt
|   |   `-- research_readiness_report.json
|   `-- repository_minimization/
|       |-- archive_manifest.json
|       |-- dataset_cleanup_plan.md
|       |-- dataset_inventory.json
|       |-- github_engineering_audit.json
|       |-- github_engineering_audit_before.json
|       |-- github_inclusion_audit.json
|       |-- github_polish_moves.json
|       |-- github_release_readiness_report.json
|       |-- github_repository_tree.md
|       `-- repository_minimization_summary.md
|-- showcase/
|   |-- architecture/
|   |   |-- architecture_diagram.png
|   |   |-- architecture_summary.md
|   |   |-- digital_twin_story.png
|   |   `-- orthotwin_pipeline_timeline.png
|   |-- dashboards/
|   |   |-- executive_dashboard.png
|   |   |-- outcome_comparison_dashboard.png
|   |   |-- state_change_dashboard.png
|   |   |-- surgery_comparison_dashboard.png
|   |   `-- surgery_ranking_dashboard.png
|   |-- graph/
|   |   |-- graph_explanation.png
|   |   `-- spine_graph_presentation.png
|   |-- hero/
|   |   |-- digital_twin_story.png
|   |   |-- hero_gallery.md
|   |   |-- implant_before_after.png
|   |   |-- mesh_displacement_heatmap_implant.png
|   |   |-- patient_alpha_showcase.png
|   |   `-- surgery_comparison_dashboard.png
|   |-- limitations/
|   |   |-- calibration_decision_flowchart.png
|   |   |-- limitations_summary.md
|   |   |-- orthotwin_poster.png
|   |   `-- spacing_candidate_dashboard.png
|   |-- measurements/
|   |   |-- alignment_visualization.png
|   |   |-- curvature_visualization.png
|   |   |-- disc_height_comparison.png
|   |   `-- measurement_dashboard.png
|   |-- mesh/
|   |   |-- mesh_before_after.png
|   |   |-- mesh_change_heatmap.png
|   |   |-- mesh_displacement_heatmap_alignment.png
|   |   |-- mesh_displacement_heatmap_implant.png
|   |   |-- mesh_displacement_heatmap_spacer.png
|   |   `-- mesh_showcase.md
|   |-- ppt_assets/
|   |   |-- 01_problem/
|   |   |-- 02_segmentation/
|   |   |-- 03_reconstruction/
|   |   |-- 04_measurements/
|   |   |-- 05_state/
|   |   |-- 06_graph/
|   |   |-- 07_surgery/
|   |   |-- 08_mesh/
|   |   |-- 09_results/
|   |   |-- 10_limitations/
|   |   |-- 11_future/
|   |   `-- README.md
|   |-- reconstruction/
|   |   |-- reconstruction_full.png
|   |   |-- reconstruction_gallery.png
|   |   `-- reconstruction_labeled.png
|   |-- reports/
|   |   |-- demo_script.md
|   |   |-- orthotwin_master_audit.md
|   |   |-- orthotwin_master_audit.pdf
|   |   |-- orthotwin_showcase_report.md
|   |   |-- orthotwin_v1_classification.json
|   |   |-- ORTHOTWIN_V1_EXECUTIVE_SUMMARY.md
|   |   |-- ORTHOTWIN_V1_RELEASE_NOTES.md
|   |   |-- phase95_calibration_audit.txt
|   |   |-- physical_calibration_decision.json
|   |   `-- ppt_storyboard.md
|   |-- segmentation/
|   |   |-- segmentation_comparison.png
|   |   |-- segmentation_pipeline.png
|   |   `-- segmentation_statistics.png
|   |-- state/
|   |   |-- digital_twin_explainer.md
|   |   |-- digital_twin_overview.png
|   |   |-- digital_twin_story.png
|   |   `-- state_vector_visualization.png
|   |-- surgery/
|   |   |-- alignment_before_after.png
|   |   |-- alignment_centerline_comparison.png
|   |   |-- fusion_before_after.png
|   |   |-- fusion_relationship_visualization.png
|   |   |-- implant_before_after.png
|   |   |-- implant_difference_heatmap.png
|   |   |-- spacer_before_after.png
|   |   |-- spacer_difference_heatmap.png
|   |   `-- surgery_showcase.md
|   |-- ORTHOTWIN_SHOWCASE_SUMMARY.md
|   |-- README.md
|   |-- showcase_figure_ranking.json
|   |-- showcase_manifest.json
|   `-- showcase_validation.json
|-- simulation/
|   |-- __pycache__/
|   |-- biomechanics/
|   |   |-- __pycache__/
|   |   |-- biomechanics_engine.py
|   |   |-- outcome_comparator.py
|   |   |-- phase4_radiology_measurement_engine.py
|   |   |-- physical_units_engine.py
|   |   `-- stage3_biomechanics_engine.py
|   |-- interventions/
|   |   `-- simulation_engine.py
|   |-- mesh/
|   |   |-- __pycache__/
|   |   |-- __init__.py
|   |   |-- mesh_state_builder.py
|   |   |-- mesh_transformation_engine.py
|   |   `-- phase8_mesh_level_engine.py
|   |-- propagation/
|   |   |-- __pycache__/
|   |   |-- propagation_engine.py
|   |   |-- propagation_rules.json
|   |   |-- stage2_engine.py
|   |   `-- state_transition.py
|   |-- surgery/
|   |   |-- __pycache__/
|   |   |-- __init__.py
|   |   |-- anatomical_modification_engine.py
|   |   |-- fusion_simulation_v2.py
|   |   |-- implant_simulation_v2.py
|   |   |-- phase7_geometry_aware_surgery_engine.py
|   |   |-- spacer_simulation.py
|   |   |-- state_rebuilder.py
|   |   |-- surgical_objects.py
|   |   `-- surgical_outcome_comparator.py
|   |-- longitudinal_engine.py
|   |-- scenario_comparator.py
|   `-- scenario_engine.py
|-- state/
|   |-- future_states/
|   |   |-- future_state_disc_collapse_10.json
|   |   |-- future_state_disc_collapse_20.json
|   |   |-- future_state_disc_collapse_30.json
|   |   |-- future_state_disc_restore_10.json
|   |   |-- future_state_disc_restore_20.json
|   |   |-- future_state_disc_restore_30.json
|   |   |-- future_state_fusion_l4_l5.json
|   |   |-- future_state_fusion_l5_s1.json
|   |   |-- future_state_implant_disc_5.json
|   |   `-- future_state_implant_disc_6.json
|   |-- graphs/
|   |   |-- disc_relationships.json
|   |   |-- spine_centerline.json
|   |   `-- spine_graph.json
|   |-- longitudinal/
|   |   |-- future_state_0_months.json
|   |   |-- future_state_10_years.json
|   |   |-- future_state_1_year.json
|   |   |-- future_state_2_years.json
|   |   |-- future_state_5_years.json
|   |   |-- future_state_6_months.json
|   |   |-- natural_progression_rules.json
|   |   `-- time_model.json
|   |-- mesh/
|   |   |-- collapse_mesh_result.json
|   |   |-- fusion_mesh_result.json
|   |   |-- implant_mesh_result.json
|   |   |-- mesh_inventory.json
|   |   |-- mesh_rebuilt_state.json
|   |   |-- mesh_rebuilt_state_collapse.json
|   |   |-- mesh_rebuilt_state_fusion.json
|   |   |-- mesh_rebuilt_state_implant.json
|   |   |-- mesh_rebuilt_state_spacer.json
|   |   |-- mesh_state_vector.json
|   |   `-- spacer_mesh_result.json
|   |-- patient_states/
|   |   |-- clinical_state_vector.json
|   |   |-- patient_state_after_intervention.json
|   |   |-- patient_state_vector.json
|   |   `-- patient_state_vector_v2.json
|   |-- scenarios/
|   |   |-- baseline_scenario.json
|   |   |-- disc_collapse_10.json
|   |   |-- disc_collapse_20.json
|   |   |-- disc_collapse_30.json
|   |   |-- disc_restoration_10.json
|   |   |-- disc_restoration_20.json
|   |   |-- disc_restoration_30.json
|   |   |-- fusion_l4_l5.json
|   |   |-- fusion_l5_s1.json
|   |   |-- implant_disc_5.json
|   |   |-- implant_disc_6.json
|   |   `-- scenario_schema.json
|   |-- surgery/
|   |   |-- alignment_geometry_result.json
|   |   |-- fusion_geometry_result.json
|   |   |-- implant_geometry_result.json
|   |   |-- rebuilt_state_alignment_correction.json
|   |   |-- rebuilt_state_fusion.json
|   |   |-- rebuilt_state_implant.json
|   |   |-- rebuilt_state_spacer.json
|   |   |-- spacer_geometry_result.json
|   |   |-- surgical_object_schema.json
|   |   `-- surgical_objects.json
|   |-- transitions/
|   |   |-- cascade_analysis.json
|   |   |-- disc_collapse_simulation.json
|   |   |-- disc_restoration_simulation.json
|   |   |-- fusion_simulation.json
|   |   |-- implant_simulation.json
|   |   `-- whole_spine_delta_report.json
|   `-- master_digital_twin_state.json
|-- tools/
|   |-- __pycache__/
|   |-- final_github_polish.py
|   |-- generate_master_technical_audit.py
|   |-- generate_showcase_edition.py
|   |-- generate_showcase_package.py
|   |-- generate_simulation_visualization_suite.py
|   |-- generate_v1_release_package.py
|   |-- github_inclusion_audit.py
|   |-- minimize_repository.py
|   `-- phase95_calibration_recovery.py
|-- visualization/
|   |-- calibration/
|   |   |-- calibration_decision_flowchart.png
|   |   |-- metadata_lineage_graph.png
|   |   |-- patient_alpha_linkage_graph.png
|   |   `-- spacing_candidate_dashboard.png
|   |-- longitudinal/
|   |   |-- progression_alignment.png
|   |   |-- progression_curvature.png
|   |   |-- progression_disc_height.png
|   |   `-- progression_load_distribution.png
|   |-- mesh/
|   |   |-- 3d_mesh_overlays.png
|   |   |-- collapse_mesh_before_after.png
|   |   |-- fusion_mesh_before_after.png
|   |   |-- implant_mesh_before_after.png
|   |   `-- spacer_mesh_before_after.png
|   |-- presentation/
|   |   |-- alignment_demo.png
|   |   |-- alignment_visualization.png
|   |   |-- curvature_visualization.png
|   |   |-- digital_twin_overview.png
|   |   |-- disc_height_comparison.png
|   |   |-- disc_volume_comparison.png
|   |   |-- executive_dashboard.png
|   |   |-- fusion_demo.png
|   |   |-- graph_explanation.png
|   |   |-- implant_demo.png
|   |   |-- measurement_dashboard.png
|   |   |-- mesh_before_after.png
|   |   |-- mesh_change_heatmap.png
|   |   |-- mesh_displacement_map.png
|   |   |-- orthotwin_pipeline_timeline.png
|   |   |-- orthotwin_poster.png
|   |   |-- outcome_comparison_dashboard.png
|   |   |-- reconstruction_exploded.png
|   |   |-- reconstruction_full.png
|   |   |-- reconstruction_gallery.png
|   |   |-- reconstruction_labeled.png
|   |   |-- segmentation_comparison.png
|   |   |-- segmentation_pipeline.png
|   |   |-- segmentation_statistics.png
|   |   |-- spacer_demo.png
|   |   |-- spine_graph_presentation.png
|   |   |-- state_vector_visualization.png
|   |   `-- surgery_ranking_dashboard.png
|   |-- reconstruction/
|   |   |-- patient_alpha_reconstruction_matplotlib_angled.png
|   |   |-- patient_alpha_reconstruction_matplotlib_front.png
|   |   `-- patient_alpha_reconstruction_matplotlib_side.png
|   |-- release/
|   |   |-- architecture_diagram.png
|   |   `-- architecture_diagram_error.txt
|   |-- segmentation/
|   |   |-- candidate_patient.png
|   |   |-- patient_alpha_gt_mask_slice_8.png
|   |   |-- patient_alpha_mri_slice_8.png
|   |   |-- patient_alpha_overlay_slice_8.png
|   |   |-- patient_alpha_pred_mask_slice_8.png
|   |   `-- weighted_loss_results.png
|   |-- simulation/
|   |   |-- affected_structures_map.png
|   |   |-- before_after_alignment_plot.png
|   |   |-- future_state_graph.png
|   |   |-- intervention_comparison.png
|   |   |-- load_redistribution_plot.png
|   |   |-- propagation_comparison.png
|   |   |-- propagation_graph.png
|   |   `-- scenario_heatmap.png
|   |-- simulation_suite/
|   |   |-- showcase_gallery/
|   |   |-- alignment_before_after.png
|   |   |-- alignment_centerline_comparison.png
|   |   |-- digital_twin_story.png
|   |   |-- fusion_before_after.png
|   |   |-- fusion_relationship_visualization.png
|   |   |-- implant_before_after.png
|   |   |-- implant_difference_heatmap.png
|   |   |-- mesh_displacement_heatmap_alignment.png
|   |   |-- mesh_displacement_heatmap_implant.png
|   |   |-- mesh_displacement_heatmap_spacer.png
|   |   |-- patient_alpha_showcase.png
|   |   |-- simulation_visualization_manifest.json
|   |   |-- simulation_visualization_summary.txt
|   |   |-- spacer_before_after.png
|   |   |-- spacer_difference_heatmap.png
|   |   |-- state_change_dashboard.png
|   |   |-- surgery_comparison_dashboard.png
|   |   `-- visualization_inventory.json
|   |-- state/
|   |   |-- alignment_changes.png
|   |   |-- alignment_plot.png
|   |   |-- centerline_plot.png
|   |   |-- disc_changes.png
|   |   |-- load_distribution_plot.png
|   |   |-- phase4_canal_area_plot.png
|   |   |-- phase4_curvature_plot.png
|   |   |-- phase4_disc_height_plot.png
|   |   |-- phase4_foraminal_area_plot.png
|   |   |-- phase4_slippage_plot.png
|   |   |-- relative_disc_height_plot.png
|   |   |-- relative_volume_plot.png
|   |   |-- spine_graph.png
|   |   |-- state_comparison.png
|   |   `-- visualization.py
|   |-- surgery/
|   |   |-- alignment_before_after.png
|   |   |-- fusion_before_after.png
|   |   |-- implant_before_after.png
|   |   |-- spacer_before_after.png
|   |   `-- surgical_heatmap.png
|   |-- alignment_changes.png
|   |-- disc_changes.png
|   `-- state_comparison.png
|-- .gitignore
|-- __init__.py
|-- CITATION.cff
|-- CODE_OF_CONDUCT.md
|-- comparison.py
|-- CONTRIBUTING.md
|-- demo.py
|-- digital_twin.py
|-- LICENSE
|-- ORTHOTWIN_V1_EXECUTIVE_SUMMARY.md
|-- ORTHOTWIN_V1_RELEASE_NOTES.md
|-- README.md
|-- README_AUDIT.json
|-- README_QUALITY_SCORE.txt
|-- repository_refactor.py
|-- requirements.txt
|-- SECURITY.md
`-- state_builder.py
```