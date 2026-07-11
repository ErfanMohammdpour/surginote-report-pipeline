/**
 * Annotation History Domain Model
 * Represents an annotation history entry with business logic
 * Following Domain-Driven Design principles
 */

/**
 * AnnotationHistoryModel Class
 * Encapsulates annotation history data and behavior
 */
export class AnnotationHistoryModel {
  constructor(data) {
    this.id = data.id;
    this.videoId = data.video_id;
    this.userId = data.user_id;
    this.createdBy = data.created_by;
    this.annotationData = data.annotation_data;
    this.description = data.description || null;
    this.createdAt = new Date(data.created_at);
    this.userFirstName = data.user_first_name;
    this.userLastName = data.user_last_name;
    this.userEmail = data.user_email;
  }

  /**
   * Get creator display name
   * Prioritizes created_by field over user's name
   * @returns {string}
   */
  getCreatorDisplayName() {
    // Always use created_by if it exists, as it's the name entered by the user
    if (this.createdBy && this.createdBy.trim()) {
      return this.createdBy.trim();
    }
    // Fallback to user's name if created_by is not available
    if (this.userFirstName && this.userLastName) {
      return `${this.userFirstName} ${this.userLastName}`;
    }
    return this.userEmail || 'Unknown';
  }

  /**
   * Get formatted creation date
   * @returns {string}
   */
  getFormattedDate() {
    const now = new Date();
    const diffMs = now - this.createdAt;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) {
      return 'Just now';
    } else if (diffMins < 60) {
      return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
    } else if (diffHours < 24) {
      return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    } else if (diffDays < 7) {
      return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    } else {
      return this.createdAt.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    }
  }

  /**
   * Get full formatted date and time
   * @returns {string}
   */
  getFullFormattedDate() {
    return this.createdAt.toLocaleString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  /**
   * Parse annotation data
   * @returns {Object|null}
   */
  getParsedAnnotationData() {
    try {
      return JSON.parse(this.annotationData);
    } catch (error) {
      console.warn('Failed to parse annotation data:', error);
      return null;
    }
  }

  /**
   * Check if annotation belongs to current user
   * @param {number} currentUserId - Current user ID
   * @returns {boolean}
   */
  belongsToUser(currentUserId) {
    return this.userId === currentUserId;
  }

  /**
   * Convert to plain object for API calls
   * @returns {Object}
   */
  toJSON() {
    return {
      id: this.id,
      video_id: this.videoId,
      user_id: this.userId,
      created_by: this.createdBy,
      annotation_data: this.annotationData,
      created_at: this.createdAt.toISOString(),
      user_first_name: this.userFirstName,
      user_last_name: this.userLastName,
      user_email: this.userEmail,
    };
  }

  /**
   * Create AnnotationHistoryModel from API response
   * @static
   * @param {Object} apiData - Raw API response data
   * @returns {AnnotationHistoryModel}
   */
  static fromAPI(apiData) {
    return new AnnotationHistoryModel(apiData);
  }

  /**
   * Create multiple AnnotationHistoryModels from API response
   * @static
   * @param {Array} apiDataArray - Array of API response data
   * @returns {Array<AnnotationHistoryModel>}
   */
  static fromAPIList(apiDataArray) {
    return apiDataArray.map((data) => AnnotationHistoryModel.fromAPI(data));
  }
}

export default AnnotationHistoryModel;
