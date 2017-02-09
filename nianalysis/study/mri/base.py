from nipype.pipeline import engine as pe
from nipype.interfaces import fsl
from nianalysis.dataset import DatasetSpec
from nianalysis.study.base import Study, set_dataset_specs
from nianalysis.requirements import Requirement
from nianalysis.citations import fsl_cite, bet_cite, bet2_cite
from nianalysis.data_formats import nifti_gz_format
from nianalysis.requirements import fsl5_req
from nipype.interfaces.fsl import FLIRT, FNIRT, Reorient2Std
from nianalysis.utils import get_atlas_path
from nianalysis.exceptions import NiAnalysisError


class MRStudy(Study):

    def brain_mask_pipeline(self, **options):  # @UnusedVariable
        """
        Generates a whole brain mask using FSL's BET command
        """
        pipeline = self._create_pipeline(
            name='brain_mask',
            inputs=['primary'],
            outputs=['masked', 'brain_mask'],
            description="Generate brain mask from mr_scan",
            default_options={'robust': False, 'threshold': 0.5,
                             'reduce_bias': False},
            requirements=[Requirement('fsl', min_version=(0, 5, 0))],
            citations=[fsl_cite, bet_cite, bet2_cite], approx_runtime=5,
            options=options)
        # Create mask node
        bet = pe.Node(interface=fsl.BET(), name="bet")
        bet.inputs.mask = True
        if pipeline.option('robust'):
            bet.inputs.robust = True
        if pipeline.option('reduce_bias'):
            bet.inputs.reduce_bias = True
        bet.inputs.frac = pipeline.option('threshold')
        # Connect inputs/outputs
        pipeline.connect_input('primary', bet, 'in_file')
        pipeline.connect_output('masked', bet, 'out_file')
        pipeline.connect_output('brain_mask', bet, 'mask_file')
        # Check inputs/outputs are connected
        pipeline.assert_connected()
        return pipeline

    def coregister_to_atlas_pipeline(self, atlas_reg_tool='fnirt',
                                     **options):
        if atlas_reg_tool == 'fnirt':
            pipeline = self._fsl_fnirt_to_atlas_pipeline(**options)
        else:
            raise NiAnalysisError("Unrecognised coregistration tool '{}'"
                                  .format(atlas_reg_tool))
        return pipeline

    def _fsl_fnirt_to_atlas_pipeline(self, **options):  # @UnusedVariable @IgnorePep8
        """
        Registers a MR scan to a refernce MR scan using FSL's nonlinear FNIRT
        command

        Parameters
        ----------
        atlas : Which atlas to use, can be one of 'mni_nl6'
        """
        pipeline = self._create_pipeline(
            name='coregister_to_atlas_fnirt',
            inputs=['primary', 'brain_mask', 'masked'],
            outputs=['coreg_to_atlas', 'coreg_to_atlas_coeff'],
            description=("Nonlinearly registers a MR scan to a standard space,"
                         "e.g. MNI-space"),
            default_options={'atlas': 'MNI152',
                             'resolution': '2mm',
                             'intensity_model': 'global_non_linear_with_bias',
                             'subsampling': [4, 4, 2, 2, 1, 1]},
            requirements=[fsl5_req],
            citations=[fsl_cite],
            approx_runtime=5,
            options=options)
        # Get the reference atlas from FSL directory
        ref_atlas = get_atlas_path(pipeline.option('atlas'), 'image',
                                   resolution=pipeline.option('resolution'))
        ref_mask = get_atlas_path(pipeline.option('atlas'), 'mask_dilated',
                                  resolution=pipeline.option('resolution'))
        ref_masked = get_atlas_path(pipeline.option('atlas'), 'masked',
                                    resolution=pipeline.option('resolution'))
        # Basic reorientation to standard MNI space
        reorient = pe.Node(Reorient2Std(), name='reorient')
        reorient_mask = pe.Node(Reorient2Std(), name='reorient_mask')
        reorient_masked = pe.Node(Reorient2Std(), name='reorient_masked')
        # Affine transformation to MNI space
        flirt = pe.Node(interface=FLIRT(), name='flirt')
        flirt.inputs.reference = ref_masked
        flirt.inputs.dof = 12
        # Nonlinear transformation to MNI space
        fnirt = pe.Node(interface=FNIRT(), name='fnirt')
        fnirt.inputs.ref_file = ref_atlas
        fnirt.inputs.refmask_file = ref_mask
        intensity_model = pipeline.option('intensity_model')
        if intensity_model is None:
            intensity_model = 'none'
        fnirt.inputs.intensity_mapping_model = intensity_model
        fnirt.inputs.subsampling_scheme = pipeline.option('subsampling')
        fnirt.inputs.fieldcoeff_file = True
        fnirt.inputs.in_fwhm = [8, 6, 5, 4.5, 3, 2]
        fnirt.inputs.ref_fwhm = [8, 6, 5, 4, 2, 0]
        fnirt.inputs.regularization_lambda = [300, 150, 100, 50, 40, 30]
        fnirt.inputs.apply_intensity_mapping = [1, 1, 1, 1, 1, 0]
        fnirt.inputs.max_nonlin_iter = [5, 5, 5, 5, 5, 10]
        # Apply mask if corresponding subsampling scheme is 1
        # (i.e. 1-to-1 resolution) otherwise don't.
        apply_mask = [int(s == 1) for s in pipeline.option('subsampling')]
        fnirt.inputs.apply_inmask = apply_mask
        fnirt.inputs.apply_refmask = apply_mask
        # Connect nodes
        pipeline.connect(reorient_masked, 'out_file', flirt, 'in_file')
        pipeline.connect(reorient, 'out_file', fnirt, 'in_file')
        pipeline.connect(reorient_mask, 'out_file', fnirt, 'inmask_file')
        pipeline.connect(flirt, 'out_matrix_file', fnirt, 'affine_file')
        # Set registration options
        # TODO: Need to work out which options to use
        # Connect inputs
        pipeline.connect_input('primary', reorient, 'in_file')
        pipeline.connect_input('brain_mask', reorient_mask, 'in_file')
        pipeline.connect_input('masked', reorient_masked, 'in_file')
        # Connect outputs
        pipeline.connect_output('coreg_to_atlas', fnirt, 'warped_file')
        pipeline.connect_output('coreg_to_atlas_coeff', fnirt,
                                'fieldcoeff_file')
        pipeline.assert_connected()
        return pipeline

    _dataset_specs = set_dataset_specs(
        DatasetSpec('primary', nifti_gz_format),
        DatasetSpec('masked', nifti_gz_format, brain_mask_pipeline),
        DatasetSpec('brain_mask', nifti_gz_format, brain_mask_pipeline),
        DatasetSpec('coreg_to_atlas', nifti_gz_format,
                    coregister_to_atlas_pipeline),
        DatasetSpec('coreg_to_atlas_coeff', nifti_gz_format,
                    coregister_to_atlas_pipeline))
